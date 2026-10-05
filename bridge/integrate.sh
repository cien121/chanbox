#!/bin/bash
# ChanBox sing-box-lx 集成脚本
# 用带 XHTTP 的 sing-box-lx 替换原版 sing-box，加 with_xhttp 编译标签
# Karing 已验证此方案在 Android 可行
set -e

LX_REPO="https://github.com/Leadaxe/sing-box-lx.git"
LX_TAG="v1.14.2-lx.11"

echo ">>> [sing-box-lx] 当前目录: $(pwd)"

# sing-box 在 nekobox 的同级目录（libcore/go.mod: replace => ../../sing-box）
SING_BOX_DIR="../sing-box"

if [ -d "$SING_BOX_DIR" ]; then
  echo ">>> [sing-box-lx] 删除原版 sing-box"
  rm -rf "$SING_BOX_DIR"
fi

echo ">>> [sing-box-lx] clone $LX_TAG（含 submodules，XHTTP 依赖它们）"
git clone --recurse-submodules --depth 1 --branch "$LX_TAG" "$LX_REPO" "$SING_BOX_DIR"

echo ">>> [sing-box-lx] 校验 XHTTP 代码存在"
if [ ! -d "$SING_BOX_DIR/transport/v2rayxhttp" ]; then
  echo "ERROR: transport/v2rayxhttp 不存在"
  exit 1
fi
if [ ! -f "$SING_BOX_DIR/option/v2ray_xhttp.go" ]; then
  echo "ERROR: option/v2ray_xhttp.go 不存在"
  exit 1
fi
echo ">>> [sing-box-lx] XHTTP 代码确认"

echo ">>> [sing-box-lx] 给 libcore/build.sh 加 with_xhttp 标签"
BUILD_SH="libcore/build.sh"
if [ ! -f "$BUILD_SH" ]; then
  echo "ERROR: $BUILD_SH 不存在"
  exit 1
fi

if grep -q "with_xhttp" "$BUILD_SH"; then
  echo ">>> [sing-box-lx] with_xhttp 已存在，跳过"
else
  # 在 with_clash_api 后追加 with_xhttp
  sed -i 's/with_clash_api/with_clash_api,with_xhttp/g' "$BUILD_SH"
  echo ">>> [sing-box-lx] 标签已追加"
fi

echo ">>> [sing-box-lx] build.sh 标签行："
grep -o 'with_[a-z_]*' "$BUILD_SH" | tr '\n' ',' | head -c 300
echo ""

# ---- #28 修复 1/3：补齐 lx submodule 的 replace ----
# Go 只认主模块（libcore）go.mod 里的 replace，lx 自带 go.mod 里的本地 replace 会被忽略。
# lx 的 wireguard-go / sing-tun / gvisor / utls 都是本地 submodule fork
#（utls-firefox148 是 REALITY X25519MLKEM768 必需的），必须在主模块里重新声明。
echo ">>> [sing-box-lx] 补齐 lx submodule 的 replace"
GO_MOD="libcore/go.mod"
for pair in \
  "github.com/sagernet/wireguard-go => ../../sing-box/submodules/wireguard-go" \
  "github.com/sagernet/sing-tun => ../../sing-box/submodules/sing-tun" \
  "github.com/sagernet/gvisor => ../../sing-box/submodules/gvisor" \
  "github.com/metacubex/utls => ../../sing-box/submodules/utls"; do
  lhs="${pair%% => *}"
  if grep -qE "^replace[[:space:]]+${lhs}[[:space:]]" "$GO_MOD"; then
    echo ">>> [sing-box-lx] replace 已存在，跳过: $lhs"
  else
    echo "replace $pair" >> "$GO_MOD"
    echo ">>> [sing-box-lx] 已追加: replace $pair"
  fi
done

# ---- #28 修复 2/3：gomobile bind 前先 go mod tidy ----
# lx 1.14 的依赖与 NekoBox 1.12 的 go.mod/go.sum 对不上，
# bind 会直接报 "go: updates to go.mod needed; to update it: go mod tidy"（#27 失败点）。
if grep -q "go mod tidy" "$BUILD_SH"; then
  echo ">>> [sing-box-lx] go mod tidy 已存在，跳过"
else
  BIND_LINE=$(grep -n 'gomobile-matsuri bind' "$BUILD_SH" | head -1 | cut -d: -f1)
  if [ -z "$BIND_LINE" ]; then
    echo "ERROR: build.sh 里找不到 gomobile-matsuri bind 行"
    exit 1
  fi
  sed -i "${BIND_LINE}i go mod tidy || exit 1" "$BUILD_SH"
  echo ">>> [sing-box-lx] go mod tidy 已插入到 bind 之前"
fi

# ---- #28 修复 3/3：get_source.sh 跳过原版 sing-box checkout ----
# get_source.sh 会 git checkout aed32ee（NekoBox 原版 commit），lx clone 里没有这个对象，
# 失败后 set -e 直接中止脚本，连带 libneko 也没 clone（#27 的连锁问题）。
GET_SOURCE="buildScript/lib/core/get_source.sh"
if grep -q 'sing-box-lx] 跳过原版' "$GET_SOURCE"; then
  echo ">>> [sing-box-lx] get_source.sh 补丁已存在，跳过"
else
  sed -i 's|^git checkout "$COMMIT_SING_BOX"$|if git rev-parse -q --verify "${COMMIT_SING_BOX}^{commit}" >/dev/null; then git checkout "$COMMIT_SING_BOX"; else echo ">>> [sing-box-lx] 跳过原版 sing-box checkout，保留 lx"; fi|' "$GET_SOURCE"
  echo ">>> [sing-box-lx] get_source.sh 已打补丁"
fi


# ---- #29 修复：移植 NekoBox 专用包到 lx 树 ----
# libcore（NekoBox 版）引用了 MatsuriDayo/sing-box fork 的 4 个独有包，
# 上游/lx 树里没有：boxapi、common/conntrack、experimental/libbox/platform、nekoutils。
# #28 死在这里："does not contain package .../boxapi" 等。
# 从原版 fork 的 1.12.19-neko-1 (aed32ee) 取这 4 个目录拷进 lx 树。
# 其中 boxapi 需补 RoutedFlow 方法：lx 1.14 的 adapter.ConnectionTracker
# 比 1.12 多了 RoutedFlow(tun 流量统计)，实现抄上游 experimental/v2rayapi.StatsService。
if [ -d "$SING_BOX_DIR/boxapi" ]; then
  echo ">>> [sing-box-lx] NekoBox 专用包已存在，跳过"
else
  NEKO_SB_SHA="aed32ee3066cdbc7d471e3e0415c5134088962df"
  echo ">>> [sing-box-lx] 下载 NekoBox 版 sing-box $NEKO_SB_SHA"
  curl -sSL --retry 3 "https://codeload.github.com/MatsuriDayo/sing-box/tar.gz/${NEKO_SB_SHA}" -o /tmp/neko-sb.tgz
  rm -rf /tmp/neko-sb-orig && mkdir -p /tmp/neko-sb-orig
  tar xzf /tmp/neko-sb.tgz -C /tmp/neko-sb-orig
  NEKO_SRC="/tmp/neko-sb-orig/sing-box-${NEKO_SB_SHA}"
  for pkg in boxapi common/conntrack experimental/libbox/platform nekoutils; do
    if [ ! -d "$NEKO_SRC/$pkg" ]; then
      echo "ERROR: 原版包缺失: $pkg"
      exit 1
    fi
  done
  echo ">>> [sing-box-lx] 拷贝 4 个专用包进 lx 树"
  cp -r "$NEKO_SRC/boxapi" "$SING_BOX_DIR/boxapi"
  cp -r "$NEKO_SRC/common/conntrack" "$SING_BOX_DIR/common/conntrack"
  mkdir -p "$SING_BOX_DIR/experimental/libbox"
  cp -r "$NEKO_SRC/experimental/libbox/platform" "$SING_BOX_DIR/experimental/libbox/platform"
  cp -r "$NEKO_SRC/nekoutils" "$SING_BOX_DIR/nekoutils"
  rm -rf /tmp/neko-sb-orig /tmp/neko-sb.tgz
  echo ">>> [sing-box-lx] 专用包拷贝完成"

  echo ">>> [sing-box-lx] 给 boxapi 补 RoutedFlow（适配 lx 1.14 ConnectionTracker）"
  cat > "$SING_BOX_DIR/boxapi/routed_flow_lx.go" <<'GOEOF'
package boxapi

// sing-box-lx 移植补丁：lx 1.14 的 adapter.ConnectionTracker 比 NekoBox 1.12 版
// 多了一个 RoutedFlow 方法（tun 流量统计），此处按上游
// experimental/v2rayapi.StatsService 的实现补齐。

import (
	"context"
	"sync/atomic"

	"github.com/sagernet/sing-box/adapter"
	tun "github.com/sagernet/sing-tun"
)

var _ adapter.ConnectionTracker = (*SbStatsService)(nil)

func (s *SbStatsService) RoutedFlow(ctx context.Context, metadata adapter.InboundContext, matchedRule adapter.Rule, matchOutbound adapter.Outbound) tun.FlowTracker {
	inbound := metadata.Inbound
	user := metadata.User
	outbound := matchOutbound.Tag()
	var uplinkCounter []*atomic.Int64
	var downlinkCounter []*atomic.Int64
	countInbound := inbound != "" && s.inbounds[inbound]
	countOutbound := outbound != "" && s.outbounds[outbound]
	countUser := user != "" && s.users[user]
	if !countInbound && !countOutbound && !countUser {
		return nil
	}
	s.access.Lock()
	if countInbound {
		uplinkCounter = append(uplinkCounter, s.loadOrCreateCounter("inbound>>>"+inbound+">>>traffic>>>uplink"))
		downlinkCounter = append(downlinkCounter, s.loadOrCreateCounter("inbound>>>"+inbound+">>>traffic>>>downlink"))
	}
	if countOutbound {
		uplinkCounter = append(uplinkCounter, s.loadOrCreateCounter("outbound>>>"+outbound+">>>traffic>>>uplink"))
		downlinkCounter = append(downlinkCounter, s.loadOrCreateCounter("outbound>>>"+outbound+">>>traffic>>>downlink"))
	}
	if countUser {
		uplinkCounter = append(uplinkCounter, s.loadOrCreateCounter("user>>>"+user+">>>traffic>>>uplink"))
		downlinkCounter = append(downlinkCounter, s.loadOrCreateCounter("user>>>"+user+">>>traffic>>>downlink"))
	}
	s.access.Unlock()
	return &sbStatsFlowTracker{uplinkCounter: uplinkCounter, downlinkCounter: downlinkCounter}
}

var _ tun.FlowTracker = (*sbStatsFlowTracker)(nil)

type sbStatsFlowTracker struct {
	uplinkCounter   []*atomic.Int64
	downlinkCounter []*atomic.Int64
}

func (t *sbStatsFlowTracker) AttachFlow(handle tun.FlowHandle) {}

func (t *sbStatsFlowTracker) CountForward(n int) {
	for _, counter := range t.uplinkCounter {
		counter.Add(int64(n))
	}
}

func (t *sbStatsFlowTracker) CountReverse(n int) {
	for _, counter := range t.downlinkCounter {
		counter.Add(int64(n))
	}
}

func (t *sbStatsFlowTracker) FlowEstablished() {}

func (t *sbStatsFlowTracker) CloseFlow(reason tun.FlowCloseReason) {}
GOEOF
  echo ">>> [sing-box-lx] RoutedFlow 补丁已写入"
fi


# ---- #30 修复：libcore（NekoBox 1.12 代码）适配 lx 1.14 API ----
# #29 编译到 libcore 报 9 处 API 漂移，逐项修复：
# ① dialer.DoNotSelectInterface 已删除（lx 重构后，UsePlatformNetworkInterfaces()=false
#    时自动走简单拨号 + AutoDetectInterfaceControl 做 protect，行为等价，直接删）
# ② box.Context 新增第 6 参数 certificateProviderRegistry
# ③ wireguard 从 outbound 移到 endpoint（RegisterOutbound 不存在，删）
# ④ adapter.DNSTransport 新增 ExchangeAsync（补异步实现）
# ⑤ process.Searcher 新增 Close/ResetCache；FindProcessInfo 改返回 *adapter.ConnectionOwner
# ⑥ tun.DefaultInterfaceMonitor：MyInterface() 改为 MyInterfaces() []string
# ⑦ 新增 libcore/platform_lx.go：把 neko 风平台接口桥接成 lx 的 adapter.PlatformInterface
#    （lx 的 router/networkManager 只从 service ctx 里取 adapter.PlatformInterface），并注册
if [ -f "libcore/platform_lx.go" ]; then
  echo ">>> [sing-box-lx] libcore lx 适配补丁已存在，跳过"
else
python3 - <<'PYEOF2'
import sys

def patch(path, old, new, count=1):
    with open(path) as f:
        src = f.read()
    n = src.count(old)
    assert n == count, f"{path}: pattern found {n} times (expected {count}): {old[:70]!r}"
    src = src.replace(old, new)
    with open(path, "w") as f:
        f.write(src)
    print(f"patched {path}: {old[:60]!r}...")

# ---- libcore/box.go ----
# ① 删 dialer.DoNotSelectInterface（import + init）
patch("libcore/box.go",
      '\t"github.com/sagernet/sing-box/common/conntrack"\n\t"github.com/sagernet/sing-box/common/dialer"\n',
      '\t"github.com/sagernet/sing-box/common/conntrack"\n')
patch("libcore/box.go",
      'func init() {\n\tdialer.DoNotSelectInterface = true\n}\n\n',
      '')
# ② box.Context 加第 6 参数
patch("libcore/box.go",
      '\t\tnekoboxAndroidDNSTransportRegistry(localTransport), nekoboxAndroidServiceRegistry(),\n\t)',
      '\t\tnekoboxAndroidDNSTransportRegistry(localTransport), nekoboxAndroidServiceRegistry(),\n\t\tnekoboxAndroidCertificateProviderRegistry(),\n\t)')
# ⑦ 注册 adapter.PlatformInterface 桥接器
patch("libcore/box.go",
      '\tservice.MustRegister[platform.Interface](ctx, boxPlatformInterfaceInstance)\n',
      '\tservice.MustRegister[platform.Interface](ctx, boxPlatformInterfaceInstance)\n\tservice.MustRegister[adapter.PlatformInterface](ctx, newLXPlatformInterfaceWrapper())\n')

# ---- libcore/box_include.go ----
# ③ wireguard 已是 endpoint，删 outbound 注册
patch("libcore/box_include.go", '\twireguard.RegisterOutbound(registry)\n\n', '')
# ② 证书提供者 registry
patch("libcore/box_include.go",
      '\t"github.com/sagernet/sing-box/adapter"\n\t"github.com/sagernet/sing-box/adapter/endpoint"\n',
      '\t"github.com/sagernet/sing-box/adapter"\n\t"github.com/sagernet/sing-box/adapter/certificate"\n\t"github.com/sagernet/sing-box/adapter/endpoint"\n')
with open("libcore/box_include.go", "a") as f:
    f.write('\nfunc nekoboxAndroidCertificateProviderRegistry() *certificate.Registry {\n\treturn certificate.NewRegistry()\n}\n')
print("patched libcore/box_include.go: append nekoboxAndroidCertificateProviderRegistry")

# ---- libcore/dns_box.go ----
# ④ 补 ExchangeAsync
patch("libcore/dns_box.go",
      '\t\treturn dns.FixedResponse(message.Id, question, responseAddrs, constant.DefaultDNSTTL), nil\n\t}\n}\n',
      '\t\treturn dns.FixedResponse(message.Id, question, responseAddrs, constant.DefaultDNSTTL), nil\n\t}\n}\n\nfunc (p *platformLocalDNSTransport) ExchangeAsync(ctx context.Context, message *mDNS.Msg, callback func(response *mDNS.Msg, err error)) {\n\tgo func() {\n\t\tresponse, err := p.Exchange(ctx, message)\n\t\tcallback(response, err)\n\t}()\n}\n\nfunc (p *platformLocalDNSTransport) Reset() {}\n')

# ---- libcore/interface_monitor.go ----
# ⑥ MyInterface() string -> MyInterfaces() []string
patch("libcore/interface_monitor.go",
      'func (s *interfaceMonitorStub) MyInterface() string {\n\treturn ""\n}\n',
      'func (s *interfaceMonitorStub) MyInterfaces() []string {\n\treturn nil\n}\n')

# ---- libcore/platform_box.go ----
# ⑤ FindProcessInfo 改返回 *adapter.ConnectionOwner
patch("libcore/platform_box.go",
      'func (w *boxPlatformInterfaceWrapper) FindProcessInfo(ctx context.Context, network string, source netip.AddrPort, destination netip.AddrPort) (*process.Info, error) {',
      'func (w *boxPlatformInterfaceWrapper) FindProcessInfo(ctx context.Context, network string, source netip.AddrPort, destination netip.AddrPort) (*adapter.ConnectionOwner, error) {')
patch("libcore/platform_box.go",
      '\tpackageName, _ := intfBox.PackageNameByUid(uid)\n\treturn &process.Info{UserId: uid, PackageName: packageName}, nil\n}\n',
      '\tpackageName, _ := intfBox.PackageNameByUid(uid)\n\towner := &adapter.ConnectionOwner{UserId: uid}\n\tif packageName != "" {\n\t\towner.AndroidPackageNames = []string{packageName}\n\t}\n\treturn owner, nil\n}\n\n// process.Searcher（lx 1.14 新增）\n\nfunc (w *boxPlatformInterfaceWrapper) ResetCache() {}\n\nfunc (w *boxPlatformInterfaceWrapper) Close() error { return nil }\n')
# process 包不再使用，删 import
patch("libcore/platform_box.go",
      '\t"github.com/sagernet/sing-box/common/process"\n',
      '')

print("ALL PATCHES OK")
PYEOF2

# ---- ⑦ 新增桥接文件 libcore/platform_lx.go ----
cat > "libcore/platform_lx.go" <<'GOEOF'
package libcore

// sing-box-lx 移植桥接：把 NekoBox 风的平台接口（boxPlatformInterfaceInstance，
// 实现自 MatsuriDayo fork 的 experimental/libbox/platform.Interface，
// 已随 #29 移植进 lx 树）适配成 lx 1.14 的 adapter.PlatformInterface。
// lx 的 router / networkManager / dialer 只从 service ctx 里取
// adapter.PlatformInterface，不做这层桥接则 TUN / protect / 接口监控全部失效。

import (
	"context"
	"net/netip"
	"syscall"

	"github.com/sagernet/sing-box/adapter"
	"github.com/sagernet/sing-box/experimental/libbox/platform"
	"github.com/sagernet/sing-box/option"
	tun "github.com/sagernet/sing-tun"
	E "github.com/sagernet/sing/common/exceptions"
	"github.com/sagernet/sing/common/logger"
	N "github.com/sagernet/sing/common/network"
)

var _ adapter.PlatformInterface = (*lxPlatformInterfaceWrapper)(nil)

type lxPlatformInterfaceWrapper struct {
	platform *boxPlatformInterfaceWrapper
}

func newLXPlatformInterfaceWrapper() *lxPlatformInterfaceWrapper {
	return &lxPlatformInterfaceWrapper{platform: boxPlatformInterfaceInstance.(*boxPlatformInterfaceWrapper)}
}

func (w *lxPlatformInterfaceWrapper) Initialize(networkManager adapter.NetworkManager) error {
	return w.platform.Initialize(networkManager)
}

func (w *lxPlatformInterfaceWrapper) UsePlatformAutoDetectInterfaceControl() bool {
	return w.platform.UsePlatformAutoDetectInterfaceControl()
}

func (w *lxPlatformInterfaceWrapper) AutoDetectInterfaceControl(fd int) error {
	return w.platform.AutoDetectInterfaceControl(fd)
}

func (w *lxPlatformInterfaceWrapper) UsePlatformInterface() bool { return true }

func (w *lxPlatformInterfaceWrapper) OpenInterface(options *tun.Options, platformOptions option.TunPlatformOptions) (tun.Tun, error) {
	return w.platform.OpenTun(options, platformOptions)
}

func (w *lxPlatformInterfaceWrapper) ProcessPlatformOptions(options option.TunPlatformOptions) error {
	return nil
}

func (w *lxPlatformInterfaceWrapper) UsePlatformDefaultInterfaceMonitor() bool {
	return w.platform.UsePlatformDefaultInterfaceMonitor()
}

func (w *lxPlatformInterfaceWrapper) CreateDefaultInterfaceMonitor(logger logger.Logger) tun.DefaultInterfaceMonitor {
	return w.platform.CreateDefaultInterfaceMonitor(logger)
}

func (w *lxPlatformInterfaceWrapper) UsePlatformNetworkInterfaces() bool { return false }

func (w *lxPlatformInterfaceWrapper) NetworkInterfaces() ([]adapter.NetworkInterface, error) {
	return w.platform.Interfaces()
}

func (w *lxPlatformInterfaceWrapper) UnderNetworkExtension() bool {
	return w.platform.UnderNetworkExtension()
}

func (w *lxPlatformInterfaceWrapper) NetworkExtensionIncludeAllNetworks() bool {
	return w.platform.IncludeAllNetworks()
}

func (w *lxPlatformInterfaceWrapper) ClearDNSCache() { w.platform.ClearDNSCache() }

func (w *lxPlatformInterfaceWrapper) RequestPermissionForWIFIState() error { return nil }

func (w *lxPlatformInterfaceWrapper) ReadWIFIState(ctx context.Context) adapter.WIFIState {
	return w.platform.ReadWIFIState()
}

func (w *lxPlatformInterfaceWrapper) UsePlatformConnectionOwnerFinder() bool { return true }

func (w *lxPlatformInterfaceWrapper) FindConnectionOwner(request *adapter.FindConnectionOwnerRequest) (*adapter.ConnectionOwner, error) {
	var network string
	switch request.IpProtocol {
	case syscall.IPPROTO_TCP:
		network = N.NetworkTCP
	case syscall.IPPROTO_UDP:
		network = N.NetworkUDP
	default:
		return nil, E.New("unknown ip protocol: ", request.IpProtocol)
	}
	sourceAddr, err := netip.ParseAddr(request.SourceAddress)
	if err != nil {
		return nil, err
	}
	destinationAddr, err := netip.ParseAddr(request.DestinationAddress)
	if err != nil {
		return nil, err
	}
	return w.platform.FindProcessInfo(context.Background(), network,
		netip.AddrPortFrom(sourceAddr, uint16(request.SourcePort)),
		netip.AddrPortFrom(destinationAddr, uint16(request.DestinationPort)))
}

func (w *lxPlatformInterfaceWrapper) UsePlatformWIFIMonitor() bool { return false }

func (w *lxPlatformInterfaceWrapper) UsePlatformNotification() bool { return true }

func (w *lxPlatformInterfaceWrapper) SendNotification(notification *adapter.Notification) error {
	return w.platform.SendNotification(&platform.Notification{
		Identifier: notification.Identifier,
		TypeName:   notification.TypeName,
		TypeID:     notification.TypeID,
		Title:      notification.Title,
		Subtitle:   notification.Subtitle,
		Body:       notification.Body,
		OpenURL:    notification.OpenURL,
	})
}

func (w *lxPlatformInterfaceWrapper) CancelNotification(identifier string, typeID int32) error {
	return nil
}

func (w *lxPlatformInterfaceWrapper) MyInterfaceAddress() []netip.Addr { return nil }

func (w *lxPlatformInterfaceWrapper) UsePlatformNeighborResolver() bool { return false }

func (w *lxPlatformInterfaceWrapper) StartNeighborMonitor(listener adapter.NeighborUpdateListener) error {
	return E.New("not supported")
}

func (w *lxPlatformInterfaceWrapper) CloseNeighborMonitor(listener adapter.NeighborUpdateListener) error {
	return nil
}

func (w *lxPlatformInterfaceWrapper) UsePlatformShell() bool { return false }

func (w *lxPlatformInterfaceWrapper) CheckPlatformShell() error { return nil }

func (w *lxPlatformInterfaceWrapper) OpenShellSession(user *adapter.PlatformUser, command string, env []string, term string, rows int32, cols int32) (adapter.ShellSession, error) {
	return nil, E.New("not supported")
}

func (w *lxPlatformInterfaceWrapper) LookupUser(username string) (*adapter.PlatformUser, error) {
	return nil, E.New("not supported")
}

func (w *lxPlatformInterfaceWrapper) LookupSFTPServer() (string, error) {
	return "", E.New("not supported")
}

func (w *lxPlatformInterfaceWrapper) ReadSystemSSHHostKey() ([]byte, error) {
	return nil, E.New("not supported")
}

func (w *lxPlatformInterfaceWrapper) TailscaleHostname() string { return "" }

func (w *lxPlatformInterfaceWrapper) UsePlatformBridge() bool { return false }

func (w *lxPlatformInterfaceWrapper) CreateBridge(options adapter.BridgeOptions) (adapter.BridgeSession, error) {
	return nil, E.New("not supported")
}
GOEOF
echo ">>> [sing-box-lx] libcore lx 适配补丁完成"
fi

echo ">>> [sing-box-lx] 全部完成"

# ---- Kotlin xhttp 接线覆盖 ----
# V2RayFmt.kt（含 xhttp 解析/导出/transport 生成）与 StandardV2RayBean.java（含 xhttpMode）
# 构建时覆盖到 NekoBox 源码；Kotlin 引用的 V2RayTransportOptions_XHTTPOptions 是下方 #36 段
# 打进 SingBoxOptions.java 的手写嵌套类（V2RayTransportOptions_* 系列都不是 gomobile 生成的）
echo ">>> [kotlin] 覆盖 Kotlin 文件（xhttp 支持）"
KOTLIN_SRC="../chanbox-assets/bridge/kotlin"
KOTLIN_DST="app/src/main/java/io/nekohasekai/sagernet/fmt/v2ray"

if [ -d "$KOTLIN_SRC" ]; then
  for f in V2RayFmt.kt StandardV2RayBean.java; do
    if [ -f "$KOTLIN_SRC/$f" ]; then
      cp -f "$KOTLIN_SRC/$f" "$KOTLIN_DST/$f"
      echo ">>> [kotlin] 已覆盖 $f"
    else
      echo ">>> [kotlin] 警告: $KOTLIN_SRC/$f 不存在，跳过"
    fi
  done
else
  echo ">>> [kotlin] $KOTLIN_SRC 不存在，跳过 Kotlin 覆盖"
fi

# ---- #36 修复：SingBoxOptions.java 补 V2RayTransportOptions_XHTTPOptions ----
# #34/#35 的真正根因（之前"Go 集成部分丢失"的诊断是错的——e6e82dbd 恢复脚本后 #35 报了完全相同的错）：
# V2RayTransportOptions_XHTTPOptions 从来就不是 gomobile 生成的类。
# V2RayTransportOptions_* 系列是手写在 app/src/main/java/moe/matsuri/nb4a/SingBoxOptions.java
# 里的 Java 嵌套类（文件内 "sing-box Options 生成器已经坏了" 注释即指此），
# ddc67185 的 Kotlin 代码引用了 V2RayTransportOptions_XHTTPOptions，但这个类从未被加进去，
# 于是 :app:compilePreviewReleaseKotlin 一直报 Unresolved reference（#34/#35 同一位置失败）。
# 修复：构建时把该类打进 SingBoxOptions.java。字段对齐 sing-box-lx option.V2RayXHTTPOptions
# 的 host/path/mode；Gson 按原样序列化，lx 侧收到 {"type":"xhttp",...} 后解析进 XHTTPOptions。
echo ">>> [xhttp] 给 SingBoxOptions.java 打 XHTTPOptions 补丁"
SINGBOX_OPTIONS="app/src/main/java/moe/matsuri/nb4a/SingBoxOptions.java"
if grep -q "class V2RayTransportOptions_XHTTPOptions" "$SINGBOX_OPTIONS"; then
  echo ">>> [xhttp] XHTTPOptions 已存在，跳过"
else
python3 - <<'PYEOF3'
def patch(path, old, new, count=1):
    with open(path) as f:
        src = f.read()
    n = src.count(old)
    assert n == count, f"{path}: pattern found {n} times (expected {count})"
    src = src.replace(old, new)
    with open(path, "w") as f:
        f.write(src)
    print(f"patched {path}")

anchor = """    public static class V2RayTransportOptions_HTTPUpgradeOptions extends V2RayTransportOptions {

        public String host;

        public String path;


    }
"""

xhttp_class = """
    public static class V2RayTransportOptions_XHTTPOptions extends V2RayTransportOptions {

        public String host;

        public String path;

        public String mode;


    }
"""

patch("app/src/main/java/moe/matsuri/nb4a/SingBoxOptions.java", anchor, anchor + xhttp_class)
print("XHTTPOptions patch OK")
PYEOF3
fi


# ---- DNS 1.14 修复：迁移到新 DNS server 格式 ----
# sing-box 1.14 移除了 legacy DNS 格式，NekoBox 生成的旧格式会导致
# "decode config: dns: legacy DNS fakeip options ... removed in sing-box 1.14.0"：
#   - 顶层 dns.fakeip -> 改为 type=fakeip 的 server（inet4_range/inet6_range 内联）
#   - 无 type 的 server（address="local"/"rcode://success"/"fakeip"/纯IP）
#     -> 必须带 type（local/udp/tcp/tls/https/quic/h3/fakeip）+ server 字段
#   - address_resolver/strategy -> domain_resolver（strategy 在 1.14 已移除）
#   - dns-block（rcode://success）无对应 server 类型，-2L 用户规则改用 action=reject
#   - avoid-loopback 规则的 outbound 匹配器在 1.14 已移除，删除该规则
#     （保留会变成 match-all，遮挡后面的用户规则和 fakeip 规则）
# 补丁脚本在 ../chanbox-assets/bridge/，幂等，可重复跑。
echo ">>> [dns114] 打 DNS 1.14 格式补丁"
DNS_BRIDGE="../chanbox-assets/bridge"
for py in patch_dns_configbuilder.py patch_dns_singboxoptions.py; do
  if [ -f "$DNS_BRIDGE/$py" ]; then
    if python3 "$DNS_BRIDGE/$py"; then
      echo ">>> [dns114] $py OK"
    else
      echo "ERROR: $DNS_BRIDGE/$py 执行失败"
      exit 1
    fi
  else
    echo ">>> [dns114] 警告: $DNS_BRIDGE/$py 不存在，跳过"
  fi
done


# ---- DNS detour 修复：去掉 DNS server 的 detour=direct ----
# sing-box 1.14 在 common/dialer/detour.go 加了硬校验：DNS server 显式 detour
# 到一个 DialerOptions 全默认的空 direct outbound 时，启动直接报错
# "start dns/https[dns-direct]: detour to an empty direct outbound makes no sense"。
# NekoBox 生成的 direct outbound 永远是空的（只有 tag+type），而 dns-local /
# dns-direct 却设了 detour=TAG_DIRECT——这在 1.12 没问题，1.14 必挂。
# 注意：这不是之前 DNS 补丁引入的，原始 NekoBox 代码就有 detour=TAG_DIRECT，
# 之前只是被 decode 阶段的错误掩盖了（#39/#42/#45 修完 decode 才暴露到 start 阶段）。
# 去掉 detour 后 DNS server 用默认直连拨号器，行为与 detour 到空 direct 完全等价。
# 补丁脚本在 ../chanbox-assets/bridge/，幂等，可重复跑，必须在 [dns114] 之后执行。
echo ">>> [dnsdetour] 去掉 DNS server 的 detour=direct"
DETOUR_BRIDGE="../chanbox-assets/bridge"
for py in patch_dns_detour.py; do
  if [ -f "$DETOUR_BRIDGE/$py" ]; then
    if python3 "$DETOUR_BRIDGE/$py"; then
      echo ">>> [dnsdetour] $py OK"
    else
      echo "ERROR: $DETOUR_BRIDGE/$py 执行失败"
      exit 1
    fi
  else
    echo ">>> [dnsdetour] 警告: $DETOUR_BRIDGE/$py 不存在，跳过"
  fi
done



# ---- Inbound 1.13 修复：legacy inbound 字段迁移到 route rule actions ----
# sing-box 1.13 移除了 inbound 的 legacy 字段（sniff、sniff_override_destination、
# sniff_timeout、domain_strategy、udp_disable_domain_unmapping），NekoBox 生成的
# 旧格式会导致 "decode config: inbounds[1]: legacy inbound fields ... removed in
# sing-box 1.13.0"：
#   - sniff -> route rule {"action": "sniff"}
#   - domain_strategy -> route rule {"action": "resolve", "strategy": "..."}
#   - sniff_override_destination 在 1.13+ 已无对应物（上游移除），直接丢弃
#     （NekoBox 用 FakeIP，域名路由场景不受影响）
# 补丁脚本在 ../chanbox-assets/bridge/，幂等，可重复跑。
echo ">>> [inbound113] 打 inbound 1.13 格式补丁"
INBOUND_BRIDGE="../chanbox-assets/bridge"
for py in patch_inbound_configbuilder.py patch_inbound_singboxoptions.py; do
  if [ -f "$INBOUND_BRIDGE/$py" ]; then
    if python3 "$INBOUND_BRIDGE/$py"; then
      echo ">>> [inbound113] $py OK"
    else
      echo "ERROR: $INBOUND_BRIDGE/$py 执行失败"
      exit 1
    fi
  else
    echo ">>> [inbound113] 警告: $INBOUND_BRIDGE/$py 不存在，跳过"
  fi
done


# ---- Tun 1.10 修复：legacy tun address 字段合并到 address ----
# sing-box 1.10 把 tun 的 inet4_address/inet6_address 合并为 address
#（另有 inet4/6_route_address -> route_address，
# inet4/6_route_exclude_address -> route_exclude_address），
# 老字段在 1.12 被删除，设置会导致
# "create service: initialize inbound[0] tun[tun-in]: legacy tun address fields
#  are deprecated in sing-box 1.10.0 and removed in sing-box 1.12.0"：
#   - ConfigBuilder.kt：tun-in 的 when (ipv6Mode) 块改用 address 字段
#   - SingBoxOptions.java：Inbound_TunOptions 加 address 字段
# 补丁脚本在 ../chanbox-assets/bridge/，幂等，可重复跑。
echo ">>> [tun110] 打 tun 1.10 address 格式补丁"
TUN_BRIDGE="../chanbox-assets/bridge"
for py in patch_tun_configbuilder.py patch_tun_singboxoptions.py; do
  if [ -f "$TUN_BRIDGE/$py" ]; then
    if python3 "$TUN_BRIDGE/$py"; then
      echo ">>> [tun110] $py OK"
    else
      echo "ERROR: $TUN_BRIDGE/$py 执行失败"
      exit 1
    fi
  else
    echo ">>> [tun110] 警告: $TUN_BRIDGE/$py 不存在，跳过"
  fi
done


# ---- XHTTP 修复：补上缺失的 v2rayxhttp import ----
# sing-box-lx v1.14.2-lx.11 的 transport/v2rayxhttp/register.go 有
# `//go:build with_xhttp` 和 init() 调 v2ray.RegisterClient()，
# 但没有任何文件 import v2rayxhttp 包，init() 永不执行，
# 真机报 "create client transport: xhttp: unknown transport type: xhttp"。
# 注意：空白导入不能放在 transport/v2ray 包里——v2rayxhttp/register.go
# 本身就 import transport/v2ray，会造成 import cycle（构建 #48 已证实：
# "imports transport/v2ray from register.go: import cycle not allowed"）。
# 安全位置是顶层的 libcore 包（sing-box 里没有任何包 import libcore）：
# gobind -> libcore -> v2rayxhttp -> v2ray，无回边。
# 补丁脚本在 ../chanbox-assets/bridge/，幂等，可重复跑，
# 在 nekobox/libcore/ 下创建 xhttp_import.go（package libcore）。
echo ">>> [xhttp-import] 补 v2rayxhttp import"
XHTTP_BRIDGE="../chanbox-assets/bridge"
if [ -f "$XHTTP_BRIDGE/patch_xhttp_import.py" ]; then
  if python3 "$XHTTP_BRIDGE/patch_xhttp_import.py" "$SING_BOX_DIR" "libcore"; then
    echo ">>> [xhttp-import] patch_xhttp_import.py OK"
  else
    echo "ERROR: $XHTTP_BRIDGE/patch_xhttp_import.py 执行失败"
    exit 1
  fi
else
  echo ">>> [xhttp-import] 警告: $XHTTP_BRIDGE/patch_xhttp_import.py 不存在，跳过"
fi

# ---- 测试 URL 修复：cp.cloudflare.com 经 Cloudflare Worker 访问返回 EOF ----
# 默认测试地址 http://cp.cloudflare.com/ 是 Cloudflare 自有端点，
# 从 Worker 内网访问时连接被提前关闭，导致 URL 延迟测试报 EOF。
# 改为 http://www.msftconnecttest.com/connecttest.txt（HTTP 200 纯文本）。
# 补丁脚本在 ../chanbox-assets/bridge/，幂等，可重复跑。
echo ">>> [testurl] 打测试 URL 补丁"
TESTURL_BRIDGE="../chanbox-assets/bridge"
if [ -f "$TESTURL_BRIDGE/patch_test_url.py" ]; then
  if python3 "$TESTURL_BRIDGE/patch_test_url.py"; then
    echo ">>> [testurl] patch_test_url.py OK"
  else
    echo "ERROR: $TESTURL_BRIDGE/patch_test_url.py 执行失败"
    exit 1
  fi
else
  echo ">>> [testurl] 警告: $TESTURL_BRIDGE/patch_test_url.py 不存在，跳过"
fi


# ---- 版本 UI 修复：去掉预览版弹窗，版本号显示 a1，sing-box 版本打 tag ----
# 1. MainActivity.kt：if (isPreview) 弹窗 -> if (false && isPreview)，不再弹出
#    "本应用为预览版，可能存在诸多问题..."
# 2. SagerNet.kt：appVersionNameForDisplay 直接返回 "a1"，不再拼
#    "1.4.2 pre-1.4.2-20260202-1"
# 3. libcore/build.sh：ldflags 加
#    -X github.com/sagernet/sing-box/constant.Version=v1.14.2-lx.11，
#    关于页不再显示 "sing-box: unknown"。
# 注意 build tags 行（with_...with_xhttp）保持不动，那是 xhttp 已启用的证据。
# 补丁脚本在 ../chanbox-assets/bridge/，幂等，可重复跑。
echo ">>> [version-ui] 去预览弹窗 / 版本号 a1 / sing-box 版本号"
VERUI_BRIDGE="../chanbox-assets/bridge"
for py in patch_no_preview_dialog.py patch_version_display.py; do
  if [ -f "$VERUI_BRIDGE/$py" ]; then
    if python3 "$VERUI_BRIDGE/$py"; then
      echo ">>> [version-ui] $py OK"
    else
      echo "ERROR: $VERUI_BRIDGE/$py 执行失败"
      exit 1
    fi
  else
    echo ">>> [version-ui] 警告: $VERUI_BRIDGE/$py 不存在，跳过"
  fi
done
# sing-box 版本号打进 libcore/build.sh（在 with_xhttp 标签之后加，不冲突）
if [ -f "$VERUI_BRIDGE/patch_singbox_version.py" ]; then
  if python3 "$VERUI_BRIDGE/patch_singbox_version.py" "libcore/build.sh"; then
    echo ">>> [version-ui] patch_singbox_version.py OK"
  else
    echo "ERROR: $VERUI_BRIDGE/patch_singbox_version.py 执行失败"
    exit 1
  fi
else
  echo ">>> [version-ui] 警告: patch_singbox_version.py 不存在，跳过"
fi

