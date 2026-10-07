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


# ---- 版本 UI 修复：去掉预览版弹窗，版本号显示 a1，隐藏 sing-box 版本行 ----
# 1. MainActivity.kt：if (isPreview) 弹窗 -> if (false && isPreview)，不再弹出
#    "本应用为预览版，可能存在诸多问题..."
# 2. SagerNet.kt：appVersionNameForDisplay 直接返回 "a1"，不再拼
#    "1.4.2 pre-1.4.2-20260202-1"
# 3. AboutFragment.kt：删除显示 Libcore.versionBox() 的 sing-box 版本行，
#    关于页只保留 App 版本 a1（用户要求不显示 sing-box 版本）。
# 补丁脚本在 ../chanbox-assets/bridge/，幂等，可重复跑。
echo ">>> [version-ui] 去预览弹窗 / 版本号 a1 / 隐藏 sing-box 版本行"
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
# 隐藏关于页 sing-box 版本行
if [ -f "$VERUI_BRIDGE/patch_singbox_version.py" ]; then
  if python3 "$VERUI_BRIDGE/patch_singbox_version.py"; then
    echo ">>> [version-ui] patch_singbox_version.py OK"
  else
    echo "ERROR: $VERUI_BRIDGE/patch_singbox_version.py 执行失败"
    exit 1
  fi
else
  echo ">>> [version-ui] 警告: patch_singbox_version.py 不存在，跳过"
fi


# ---- 侧边导航菜单精简：去掉 推广/文档/关于 ----
# 用户要求侧边栏只保留 配置/分组/路由/设置/日志/工具。
# 补丁删掉 main_drawer_menu.xml 末尾的 about 分组
#（nav_tuiguang/nav_faq/nav_about），并同步清理 MainActivity.kt 里
# 对这三个 R.id 的引用（否则 R 常量消失会导致编译失败）。
# 补丁脚本在 ../chanbox-assets/bridge/，幂等，可重复跑。
echo ">>> [navmenu] 精简侧边导航菜单（去推广/文档/关于）"
NAVMENU_BRIDGE="../chanbox-assets/bridge"
if [ -f "$NAVMENU_BRIDGE/patch_nav_menu.py" ]; then
  if python3 "$NAVMENU_BRIDGE/patch_nav_menu.py"; then
    echo ">>> [navmenu] patch_nav_menu.py OK"
  else
    echo "ERROR: $NAVMENU_BRIDGE/patch_nav_menu.py 执行失败"
    exit 1
  fi
else
  echo ">>> [navmenu] 警告: patch_nav_menu.py 不存在，跳过"
fi




# ---- 默认路由规则改成 v2rayNG 的 7 条 ----
# NekoBox 首次运行时在 ProfileManager.getRules() 里创建默认路由，
# 这里替换为 v2rayNG 的默认 7 条：
#   1. 屏蔽广告 [geosite:category-ads-all] -> block
#   2. 阻断 udp443 (443/udp) -> block
#   3. 代理 Google [geosite:google] -> proxy
#   4. 绕过局域网 IP [geoip:private] -> direct
#   5. 绕过局域网域名 [geosite:private] -> direct
#   6. 绕过中国公共 DNS IP -> direct
#   7. 绕过中国公共 DNS 域名 -> direct
# 补丁脚本在 ../chanbox-assets/bridge/，幂等，可重复跑。
echo ">>> [routes] 打 v2rayNG 默认路由补丁"
ROUTES_BRIDGE="../chanbox-assets/bridge"
if [ -f "$ROUTES_BRIDGE/patch_default_routes.py" ]; then
  if python3 "$ROUTES_BRIDGE/patch_default_routes.py"; then
    echo ">>> [routes] patch_default_routes.py OK"
  else
    echo "ERROR: $ROUTES_BRIDGE/patch_default_routes.py 执行失败"
    exit 1
  fi
else
  echo ">>> [routes] 警告: patch_default_routes.py 不存在，跳过"
fi


# ---- 设置默认值对齐 v2rayNG ----
# 用户要求 ChanBox 设置页面的默认值与 v2rayNG 一致：
#   mtu: 9000 -> 1600
#   remoteDns: https://dns.google/dns-query -> 1.1.1.1
#   directDns: https://223.5.5.5/dns-query -> 223.5.5.5
#   ipv6Mode: 0 (disable) -> 2 (prefer)
#   logLevel: 0 (none) -> 1 (warn)
# 补丁脚本在 ../chanbox-assets/bridge/，幂等，可重复跑。
echo ">>> [settings] 对齐设置默认值（v2rayNG）"
SETTINGS_BRIDGE="../chanbox-assets/bridge"
if [ -f "$SETTINGS_BRIDGE/patch_settings_ui.py" ]; then
  if python3 "$SETTINGS_BRIDGE/patch_settings_ui.py"; then
    echo ">>> [settings] patch_settings_ui.py OK"
  else
    echo "ERROR: $SETTINGS_BRIDGE/patch_settings_ui.py 执行失败"
    exit 1
  fi
else
  echo ">>> [settings] 警告: patch_settings_ui.py 不存在，跳过"
fi



# ---- 服务器列表改两列显示 ----
# 用户要求主界面服务器列表改成两列网格（v2rayNG 有"应用双列显示"选项）。
# 补丁做两件事：
#   1. 新建 ktx/FixedGridLayoutManager.kt：GridLayoutManager 版的
#      FixedLinearLayoutManager（同样的 IndexOutOfBounds 保护和 FAB
#      滚动显隐行为），spanCount=2。
#   2. ConfigurationFragment.kt：import 和 layoutManager 初始化改用
#      FixedGridLayoutManager。layoutManager 字段类型保持 LinearLayoutManager
#     （GridLayoutManager 是其子类），其余用法不受影响。
# 补丁脚本在 ../chanbox-assets/bridge/，幂等，可重复跑。
echo ">>> [twocol] 服务器列表改两列显示"
TWOCOL_BRIDGE="../chanbox-assets/bridge"
if [ -f "$TWOCOL_BRIDGE/patch_two_column.py" ]; then
  if python3 "$TWOCOL_BRIDGE/patch_two_column.py"; then
    echo ">>> [twocol] patch_two_column.py OK"
  else
    echo "ERROR: $TWOCOL_BRIDGE/patch_two_column.py 执行失败"
    exit 1
  fi
else
  echo ">>> [twocol] 警告: patch_two_column.py 不存在，跳过"
fi



# ---- 主界面菜单改成 v2rayNG ----
# 用户要求主界面右上角三点菜单的项目、名称、顺序与 v2rayNG 一致：
# 服务重启、删除配置、删除重复配置、删除无效配置、将配置导出至剪贴板、
# 定位所选配置、按测试结果排序、测试 TCP 延迟（TCPing）、测试真连接延迟、更新订阅。
# 补丁改 bridge/patch_main_menu.py：
#   1. add_profile_menu.xml：重写 action_misc 子菜单（重排/改名/增删项）；
#   2. values-zh-rCN/strings.xml + values/strings.xml：重命名中文/英文文案并新增；
#   3. ConfigurationFragment.kt：删除已下架菜单的 handler，新增四个菜单项的 handler。
# 补丁脚本在 ../chanbox-assets/bridge/，幂等，可重复跑。
echo ">>> [menu] 主界面菜单对齐 v2rayNG"
MENU_BRIDGE="../chanbox-assets/bridge"
if [ -f "$MENU_BRIDGE/patch_main_menu.py" ]; then
  if python3 "$MENU_BRIDGE/patch_main_menu.py"; then
    echo ">>> [menu] patch_main_menu.py OK"
  else
    echo "ERROR: $MENU_BRIDGE/patch_main_menu.py 执行失败"
    exit 1
  fi
else
  echo ">>> [menu] 警告: patch_main_menu.py 不存在，跳过"
fi



# ---- Hysteria2 编辑界面对齐 v2rayNG ----
# 用户要求 Hysteria2 节点编辑界面的字段顺序、标签、提示文字与 v2rayNG 一致，
# 其他协议（VLESS/VMess/Trojan/Shadowsocks）的通用字段标签也一并对齐。
# 补丁改 bridge/patch_hy2_ui.py：
#   1. hysteria_preferences.xml：字段按 v2rayNG 顺序重排
#      （地址→端口→密码→混淆密码→端口跳跃间隔→带宽下行→带宽上行→
#       跳过证书验证→SNI→证书；Hy1 专有字段放最后）；
#   2. values-zh-rCN/strings.xml + values/strings.xml：
#      别名 (remarks)、地址 (address)、端口 (port)、SNI、
#      跳过证书验证 (allowInsecure)、带宽上/下行等标签对齐 v2rayNG。
# 注意：echConfigList、证书指纹、FinalMask 为 v2rayNG 特有，
# sing-box Hysteria2 不支持，未添加。
# 补丁脚本在 ../chanbox-assets/bridge/，幂等，可重复跑。
echo ">>> [hy2ui] Hysteria2 编辑界面对齐 v2rayNG"
HY2UI_BRIDGE="../chanbox-assets/bridge"
if [ -f "$HY2UI_BRIDGE/patch_hy2_ui.py" ]; then
  if python3 "$HY2UI_BRIDGE/patch_hy2_ui.py"; then
    echo ">>> [hy2ui] patch_hy2_ui.py OK"
  else
    echo "ERROR: $HY2UI_BRIDGE/patch_hy2_ui.py 执行失败"
    exit 1
  fi
else
  echo ">>> [hy2ui] 警告: patch_hy2_ui.py 不存在，跳过"
fi


# ---- 应用显示名称改为 RelayBox ----
# 用户要求把应用名从 ChanBox 改为 RelayBox（仅显示名称，包名 com.chan.box 不变）。
# 注意：.github/workflows/build.yml 里有一行 sed 把 NekoBox 改成 ChanBox，
# 本补丁在 integrate.sh 里再把 ChanBox 改为 RelayBox（workflow 无权限改）。
# 补丁改 bridge/patch_app_name.py：
#   1. values/strings.xml：app_name ChanBox->RelayBox，
#      app_name_long "NekoBox for Android"->"RelayBox for Android"（关于页标题）；
#   2. CrashHandler.kt：崩溃报告头改为 RelayBox for Android；
#   3. BackupFragment.kt：备份文件名前缀改为 relaybox_backup_。
# 补丁脚本在 ../chanbox-assets/bridge/，幂等，可重复跑。
echo ">>> [appname] 应用显示名称改为 RelayBox"
APPNAME_BRIDGE="../chanbox-assets/bridge"
if [ -f "$APPNAME_BRIDGE/patch_app_name.py" ]; then
  if python3 "$APPNAME_BRIDGE/patch_app_name.py"; then
    echo ">>> [appname] patch_app_name.py OK"
  else
    echo "ERROR: $APPNAME_BRIDGE/patch_app_name.py 执行失败"
    exit 1
  fi
else
  echo ">>> [appname] 警告: patch_app_name.py 不存在，跳过"
fi


# ---- 设置页面删除"启用 Clash API"和"像 SagerNet 一样显示底栏" ----
# 用户要求删除设置页面的这两项（2026-10-05）。
# 补丁改 bridge/patch_remove_settings.py：
#   1. app/src/main/res/xml/global_preferences.xml：
#      删除 key="enableClashAPI" 和 key="showBottomBar" 的 <SwitchPreference> 块；
#      底层 DataStore/Constants 的 key 定义保留，只移除 UI 显示。
#   2. app/src/main/java/io/nekohasekai/sagernet/ui/SettingsPreferenceFragment.kt：
#      删除 findPreference<SwitchPreference>(Key.ENABLE_CLASH_API)!! 块
#      （XML 项删除后 findPreference 返回 null，!! 会导致 NPE，必须同步删除）。
# 注意：MainActivity.refreshNavMenu(DataStore.enableClashAPI) 的调用保留，
# 它用的是 DataStore 存储值（默认 false），内部用 ?. 安全调用，不会出问题。
# 补丁脚本在 ../chanbox-assets/bridge/，幂等，可重复跑。
echo ">>> [rmsettings] 删除设置页面的 Clash API 和底栏显示两项"
RMSETTINGS_BRIDGE="../chanbox-assets/bridge"
if [ -f "$RMSETTINGS_BRIDGE/patch_remove_settings.py" ]; then
  if python3 "$RMSETTINGS_BRIDGE/patch_remove_settings.py"; then
    echo ">>> [rmsettings] patch_remove_settings.py OK"
  else
    echo "ERROR: $RMSETTINGS_BRIDGE/patch_remove_settings.py 执行失败"
    exit 1
  fi
else
  echo ">>> [rmsettings] 警告: patch_remove_settings.py 不存在，跳过"
fi


# ---- 测速功能 ----
# 用户要求添加测速功能（测试选中节点的下行/上行速度）。
# 补丁改 bridge/patch_speedtest.py：
#   1. libcore/speedtest.go（新建）：downloadSpeed/uploadSpeed，经代理测带宽；
#   2. libcore/box.go：导出 SpeedTestDownload/SpeedTestUpload（仿 UrlTest 写法）；
#   3. SpeedTestFragment.kt（新建）：工具页新增"测速"标签；
#   4. SpeedTestInstance.kt（新建）：按 TestInstance 模式建单节点 box；
#   5. layout_speedtest.xml（新建）：开始/取消按钮、进度条、结果展示；
#   6. ToolsFragment.kt：加 SpeedTestFragment 标签；
#   7. values/strings.xml + values-zh-rCN/strings.xml：测速相关文案。
# 测速走 Cloudflare（__down/__up），经当前选中节点。
# 补丁脚本在 ../chanbox-assets/bridge/，幂等，可重复跑。
echo ">>> [speedtest] 添加测速功能"
SPEEDTEST_BRIDGE="../chanbox-assets/bridge"
if [ -f "$SPEEDTEST_BRIDGE/patch_speedtest.py" ]; then
  if python3 "$SPEEDTEST_BRIDGE/patch_speedtest.py"; then
    echo ">>> [speedtest] patch_speedtest.py OK"
  else
    echo "ERROR: $SPEEDTEST_BRIDGE/patch_speedtest.py 执行失败"
    exit 1
  fi
else
  echo ">>> [speedtest] 警告: patch_speedtest.py 不存在，跳过"
fi



# ---- 主题颜色精简 ----
# 用户要求主题颜色选择器只保留黑/蓝/紫三色。
# 补丁改 bridge/patch_theme_colors.py：
#   1. app/src/main/res/values/colors.xml：material_colors 数组只留
#      material_light_black / material_blue_500 / material_purple_500；
#   2. utils/Theme.kt：常量重映射 BLACK=1/BLUE=2/PURPLE=3，默认主题改 BLUE，
#      getTheme/getDialogTheme 只保留三色分支，旧的存储值 fallback 到蓝色。
# 补丁脚本在 ../chanbox-assets/bridge/，幂等，可重复跑。
echo ">>> [theme] 主题颜色选择器精简为黑/蓝/紫三色"
THEME_BRIDGE="../chanbox-assets/bridge"
if [ -f "$THEME_BRIDGE/patch_theme_colors.py" ]; then
  if python3 "$THEME_BRIDGE/patch_theme_colors.py"; then
    echo ">>> [theme] patch_theme_colors.py OK"
  else
    echo "ERROR: $THEME_BRIDGE/patch_theme_colors.py 执行失败"
    exit 1
  fi
else
  echo ">>> [theme] 警告: patch_theme_colors.py 不存在，跳过"
fi


# ---- geosite 规则集修复 ----
# 紧急修复：默认路由的 geosite:xxx 被转成 rule_set 本地文件引用
# （path="geosite:category-ads-all"），sing-box 1.14 启动时尝试打开该文件
# 导致 "no such file or directory"，服务无法启动。
# 注意：sing-box 1.14 的 route rule 不支持 geosite/geoip 字段
# （会直接报错 "deprecated ... removed in sing-box 1.12.0"）。
# 补丁改 bridge/patch_geosite_ruleset.py：
#   1. 构建时下载 sing-box + geosite.db，把 category-ads-all/google/private
#      三个分类导出并编译为 .srs 二进制规则集，打包进 APK assets/srs/；
#   2. 改 SingBoxOptionsUtil.kt 的 generateRuleSet()：geosite: 分类若有
#      内置 .srs，则复制到 no_backup/srs/ 并用绝对路径引用；未知分类跳过
#      （不再生成会导致崩溃的坏路径）。
# 补丁脚本在 ../chanbox-assets/bridge/，幂等，可重复跑。
echo ">>> [geosrs] geosite 分类打包为 .srs 规则集并修复 rule_set 路径"
GEOSRS_BRIDGE="../chanbox-assets/bridge"
if [ -f "$GEOSRS_BRIDGE/patch_geosite_ruleset.py" ]; then
  if python3 "$GEOSRS_BRIDGE/patch_geosite_ruleset.py"; then
    echo ">>> [geosrs] patch_geosite_ruleset.py OK"
  else
    echo "ERROR: $GEOSRS_BRIDGE/patch_geosite_ruleset.py 执行失败"
    exit 1
  fi
else
  echo ">>> [geosrs] 警告: patch_geosite_ruleset.py 不存在，跳过"
fi


# ---- XHTTP 快捷入口：添加节点列表加 XHTTP 项，传输下拉框加 xhttp ----
# 用户要求：手动添加节点的协议列表中加入 XHTTP 选项；VLESS 传输协议
# 下拉框（只有 tcp/ws/http/quic/grpc/httpupgrade）中加入 xhttp。
# 补丁改 bridge/patch_xhttp_menu.py（幂等，可重复跑）：
#   1. add_profile_menu.xml：手动添加子菜单中 VLESS 之后加 "XHTTP" 项；
#   2. ConfigurationFragment.kt：action_new_xhttp 打开 VMessSettingsActivity，
#      附带 vless=true + xhttp=true；
#   3. VMessSettingsActivity.kt：createEntity() 中 xhttp=true 时预设 type="xhttp"；
#   4. arrays.xml：networks_value 加 xhttp；新增 xhttp_mode_value 数组
#      (auto/packet-up/stream-up/stream-one)；
#   5. standard_v2ray_preferences.xml：加 XHTTP 模式选择器 (key=xhttpMode)；
#   6. StandardV2RaySettingsActivity.kt：绑定 xhttpMode，updateView() 加
#      xhttp 分支（显示 host/path），模式选择器仅 xhttp 时可见。
# 补丁脚本在 ../chanbox-assets/bridge/，幂等，可重复跑。
echo ">>> [xhttpmenu] XHTTP 快捷入口 + 传输下拉框 xhttp 选项"
XHTTPMENU_BRIDGE="../chanbox-assets/bridge"
if [ -f "$XHTTPMENU_BRIDGE/patch_xhttp_menu.py" ]; then
  if python3 "$XHTTPMENU_BRIDGE/patch_xhttp_menu.py"; then
    echo ">>> [xhttpmenu] patch_xhttp_menu.py OK"
  else
    echo "ERROR: $XHTTPMENU_BRIDGE/patch_xhttp_menu.py 执行失败"
    exit 1
  fi
else
  echo ">>> [xhttpmenu] 警告: patch_xhttp_menu.py 不存在，跳过"
fi


# ---- Hysteria2 ECH 支持 ----
# Hysteria v2.12.3 官方加入 ECH 支持（hysteria ech 子命令生成 ECH 密钥和客户端配置）。
# sing-box-lx v1.14.2-lx.11 的 Hysteria2 出站已支持 tls.ech（OutboundECHOptions），
# 链条已验证：Hysteria2OutboundOptions -> OutboundTLSOptionsContainer ->
# OutboundTLSOptions.ech -> tls.NewClient -> parseECHClientConfig。
# 补丁改 bridge/patch_hy2_ech.py（幂等，可重复跑）：
#   1. HysteriaBean.java：加 echConfigList 字段（序列化版本 7->8）
#   2. Constants.kt：加 SERVER_ECH_CONFIG_LIST key
#   3. DataStore.kt：加 serverECHConfigList 字段
#   4. hysteria_preferences.xml：加 echConfigList 输入框（SNI 之后）
#   5. HysteriaSettingsActivity.kt：绑定
#   6. HysteriaFmt.kt：Hy2 分支 TLS 中设置 ech（raw base64 自动包 PEM）
#   7. strings.xml（中/英）：加 ech_config_list 文案
# 补丁脚本在 ../chanbox-assets/bridge/，幂等，可重复跑。
echo ">>> [hy2ech] Hysteria2 ECH 支持"
HY2ECH_BRIDGE="../chanbox-assets/bridge"
if [ -f "$HY2ECH_BRIDGE/patch_hy2_ech.py" ]; then
  if python3 "$HY2ECH_BRIDGE/patch_hy2_ech.py"; then
    echo ">>> [hy2ech] patch_hy2_ech.py OK"
  else
    echo "ERROR: $HY2ECH_BRIDGE/patch_hy2_ech.py 执行失败"
    exit 1
  fi
else
  echo ">>> [hy2ech] 警告: patch_hy2_ech.py 不存在，跳过"
fi


# ---- Hysteria2 独立跳跃端口输入框 + 协议版本显示 ----
# 用户要求（2026-10-06）："一个独立端口，一个跳跃端口"、"增加不好吗"——
# Hy2 编辑页"端口"下方新增独立的"跳跃端口"输入框（留空=不跳跃）；
# 另按纠正把"协议版本：2"改成显示"协议：hysteria2"（改文字，不删除）。
# 补丁改 bridge/patch_hy2_hop_field.py（幂等，可重复跑）：
#   1. HysteriaBean.java：加 hopPorts 字段（序列化版本 8->9）
#   2. Constants.kt：加 SERVER_HOP_PORTS key
#   3. DataStore.kt：加 serverHopPorts 字段
#   4. hysteria_preferences.xml：serverPorts 后加跳跃端口输入框；
#      protocolVersion 的 entries 改用 hysteria_version_entries（显示 hysteria1/2）
#   5. arrays.xml：加 hysteria_version_entries 数组
#   6. HysteriaSettingsActivity.kt：绑定
#   7. HysteriaFmt.kt：Hy1/Hy2 出站按 hopPorts 生成 server_ports；mport 导入导出走 hopPorts
#   8. strings.xml（中/英）：加 hop_ports 文案；protocol_version 改名为"协议"/"Protocol"
echo ">>> [hy2hopfield] Hysteria2 独立跳跃端口"
HY2HOP_BRIDGE="../chanbox-assets/bridge"
if [ -f "$HY2HOP_BRIDGE/patch_hy2_hop_field.py" ]; then
  if python3 "$HY2HOP_BRIDGE/patch_hy2_hop_field.py"; then
    echo ">>> [hy2hopfield] patch_hy2_hop_field.py OK"
  else
    echo "ERROR: $HY2HOP_BRIDGE/patch_hy2_hop_field.py 执行失败"
    exit 1
  fi
else
  echo ">>> [hy2hopfield] 警告: patch_hy2_hop_field.py 不存在，跳过"
fi

# ---- #117 回归修复：hopPorts 空安全 ----
# #117 新增的 hopPorts 是 Java String，在 Kotlin 侧为平台类型。
# 若运行时为 null，bean.hopPorts.isNotBlank() / hopPorts.ifBlank 会抛 NPE，
# 导致延迟测试崩溃、所有节点显示失败。
# 本补丁将相关访问改为 null-safe。
echo ">>> [hy2hopfix] Hysteria2 hopPorts 空安全修复"
HY2HOPFIX_BRIDGE="../chanbox-assets/bridge"
if [ -f "$HY2HOPFIX_BRIDGE/patch_hy2_hopfield_fix.py" ]; then
  if python3 "$HY2HOPFIX_BRIDGE/patch_hy2_hopfield_fix.py"; then
    echo ">>> [hy2hopfix] patch_hy2_hopfield_fix.py OK"
  else
    echo "ERROR: $HY2HOPFIX_BRIDGE/patch_hy2_hopfield_fix.py 执行失败"
    exit 1
  fi
else
  echo ">>> [hy2hopfix] 警告: patch_hy2_hopfield_fix.py 不存在，跳过"
fi

# ---- #119 后续加固：hopPorts 跳跃端口逻辑 ----
# #119 的空安全修复已进包，但用户实测依然全部超时。深入排查（2026-10-07）确认：
# 旧"NPE 拖死整批测试"理论不成立（urlTest 按 profile 独立 try/catch）；
# 但 #117 的出站逻辑仍有真实健壮性 bug：
#   1. server_port = serverPorts.toIntOrNull() ?: 443 —— "端口"不是纯数字时凭空捏造 443；
#   2. 全链路无 trim，而 sing-box 的 ParsePorts 用 strconv.ParseUint 且不 trim，
#      用户在手机上输入 "20000 - 21000"（带空格）会使 NewClient 直接报错，出站创建失败；
#   3. hopPorts 非空但解析为空（垃圾输入）时，server_ports 未设置而 server_port 已被强制赋值。
# 本补丁：trim 输入；只在"端口"是合法单端口时才设 server_port（不再捏造）；
# hopPorts 解析为空时回退到旧 serverPorts 逻辑。
echo ">>> [hy2hopharden] Hysteria2 hopPorts 逻辑加固"
HY2HOPHARDEN_BRIDGE="../chanbox-assets/bridge"
if [ -f "$HY2HOPHARDEN_BRIDGE/patch_hy2_hopfield_harden.py" ]; then
  if python3 "$HY2HOPHARDEN_BRIDGE/patch_hy2_hopfield_harden.py"; then
    echo ">>> [hy2hopharden] patch_hy2_hopfield_harden.py OK"
  else
    echo "ERROR: $HY2HOPHARDEN_BRIDGE/patch_hy2_hopfield_harden.py 执行失败"
    exit 1
  fi
else
  echo ">>> [hy2hopharden] 警告: patch_hy2_hopfield_harden.py 不存在，跳过"
fi



# ---- 负载均衡 (urltest 自动选优) ----
# 用户要求：做负载均衡。sing-box 有 urltest 出站类型，可按延迟自动选择最优节点。
# NekoBox 已有 selector 分组模式（group.isSelector -> 生成 selector 出站）。
# 补丁改 bridge/patch_loadbalance.py（幂等，可重复跑）：
#   1. Constants.kt：加 LOAD_BALANCE key；
#   2. DataStore.kt：加 loadBalance 全局开关；
#   3. group_preferences.xml：分组设置加"负载均衡"开关（仅 selector 模式可用）；
#   4. strings.xml（中/英）：加文案；
#   5. ConfigBuilder.kt：selector 分组 + 负载均衡开时，生成 urltest 出站
#      （自动选延迟最低节点，5 分钟重测，tolerance 50ms）代替 selector。
# 补丁脚本在 ../chanbox-assets/bridge/，幂等，可重复跑。
echo ">>> [loadbalance] 负载均衡 urltest 支持"
LB_BRIDGE="../chanbox-assets/bridge"
if [ -f "$LB_BRIDGE/patch_loadbalance.py" ]; then
  if python3 "$LB_BRIDGE/patch_loadbalance.py"; then
    echo ">>> [loadbalance] patch_loadbalance.py OK"
  else
    echo "ERROR: $LB_BRIDGE/patch_loadbalance.py 执行失败"
    exit 1
  fi
else
  echo ">>> [loadbalance] 警告: patch_loadbalance.py 不存在，跳过"
fi

# 补丁改 bridge/patch_loadbalance_quick.py（幂等，可重复跑）：
#   主界面 ⋮ 菜单加"负载均衡"快捷开关（checkable），点一下直接对当前分组
#   开/关负载均衡，开启时自动把当前分组设为 selector 模式。
#   与分组设置里的开关共用 DataStore.loadBalance，互相兼容。
#   需 patch_loadbalance.py 先跑。
echo ">>> [loadbalance-quick] 主界面负载均衡快捷开关"
if [ -f "$LB_BRIDGE/patch_loadbalance_quick.py" ]; then
  if python3 "$LB_BRIDGE/patch_loadbalance_quick.py"; then
    echo ">>> [loadbalance-quick] patch_loadbalance_quick.py OK"
  else
    echo "ERROR: $LB_BRIDGE/patch_loadbalance_quick.py 执行失败"
    exit 1
  fi
else
  echo ">>> [loadbalance-quick] 警告: patch_loadbalance_quick.py 不存在，跳过"
fi


# ---- 配置面板卡片化：底部状态栏改成两张卡片 + 现代纸飞机按钮 ----
# 用户要求（2026-10-06）：配置面板改成卡片式；第一项放连接速率/负载均衡/
# IP出口，第二项放节点配置（含测速卡片）；卡片设计灵活生动、间距宽松；
# 黑底混合色；VPN 启动图标（纸飞机圆形按钮）重新设计、现代一点。
# 补丁改 bridge/patch_config_cards.py（幂等，可重复跑）：
#   1. layout_main.xml：StatsBar 内容换成两张 MaterialCardView
#      （卡片一：连接速率/负载均衡/IP出口；卡片二：节点配置+测速按钮）；
#   2. layout_main.xml：ServiceButton 改圆角方形 + 蓝色（现代样式）；
#   3. themes.xml：加 ShapeAppearance.RelayBox.FabSquircle；
#   4. StatsBar.kt：接线（实时速率、负载均衡点按切换、IP归属地查询、
#      节点卡片、卡片内 Ookla 测速）；
#   5. libcore/speedtest.go：追加 ipGeoLookup（走代理查 ip-api.com）；
#   6. libcore/box.go：导出 IPGeoLookup；
#   7. SpeedTestInstance.kt：加 doIPGeoLookup；
#   8. strings.xml（中/英）：加文案。
# 需 patch_speedtest.py / patch_loadbalance.py / patch_loadbalance_quick.py 先跑。
# 补丁脚本在 ../chanbox-assets/bridge/，幂等，可重复跑。
echo ">>> [config-cards] 配置面板卡片化 + 现代启动按钮"
CC_BRIDGE="../chanbox-assets/bridge"
if [ -f "$CC_BRIDGE/patch_config_cards.py" ]; then
  if python3 "$CC_BRIDGE/patch_config_cards.py"; then
    echo ">>> [config-cards] patch_config_cards.py OK"
  else
    echo "ERROR: $CC_BRIDGE/patch_config_cards.py 执行失败"
    exit 1
  fi
else
  echo ">>> [config-cards] 警告: patch_config_cards.py 不存在，跳过"
fi

# ---- 配置面板卡片 v4 polish：40 国旗 + 延迟质量中文 ----
# 在 v3 基础上：countryLabel 从 14 国扩展到 40 国；ping pill 追加
# 中文质量词（极速/流畅/一般/较慢）。幂等，需 v3 先跑。
echo ">>> [config-cards-v4] 卡片 v4 polish"
if [ -f "$CC_BRIDGE/patch_config_cards_v4.py" ]; then
  if python3 "$CC_BRIDGE/patch_config_cards_v4.py"; then
    echo ">>> [config-cards-v4] patch_config_cards_v4.py OK"
  else
    echo "ERROR: $CC_BRIDGE/patch_config_cards_v4.py 执行失败"
    exit 1
  fi
else
  echo ">>> [config-cards-v4] 警告: patch_config_cards_v4.py 不存在，跳过"
fi

# ---- 安装包版本号 v01（干净，不带 142） ----
# 用户要求（2026-10-06）：安装包版本号改成 v01，不要带 142。
# nb4a.properties: VERSION_NAME=1.4.2 -> v01（APK 文件名不再带 142）。
# 补丁改 bridge/patch_version_v01.py（幂等，可重复跑）。
echo ">>> [version-v01] 安装包版本号 v01"
if [ -f "$CC_BRIDGE/patch_version_v01.py" ]; then
  if python3 "$CC_BRIDGE/patch_version_v01.py"; then
    echo ">>> [version-v01] patch_version_v01.py OK"
  else
    echo "ERROR: $CC_BRIDGE/patch_version_v01.py 执行失败"
    exit 1
  fi
else
  echo ">>> [version-v01] 警告: patch_version_v01.py 不存在，跳过"
fi



# ---- 统一单页面 + 商业启动按钮 + 双栈 IP ----
# 用户要求（2026-10-06）："干脆都安排在一个页面吧，把原来nekobox的启动图标直接换成那个商业图标"。
# 追加：IP 出口同时显示 IPv4 和 IPv6；面板配色按 ZedSecure 参考图。
# 补丁改 bridge/patch_unified_page.py（幂等，可重复跑）。
echo ">>> [unified-page] 统一单页面 + 商业启动按钮 + 双栈 IP"
if [ -f "$CC_BRIDGE/patch_unified_page.py" ]; then
  if python3 "$CC_BRIDGE/patch_unified_page.py"; then
    echo ">>> [unified-page] patch_unified_page.py OK"
  else
    echo "ERROR: $CC_BRIDGE/patch_unified_page.py 执行失败"
    exit 1
  fi
else
  echo ">>> [unified-page] 警告: patch_unified_page.py 不存在，跳过"
fi


# ---- 启动键移到底部 + 底部导航栏 + 节点列表置顶 ----
# 用户要求（2026-10-06）："启动键放在最下面"；"菜单键也独立出来，放在最下面"；
# "配置、路由、设置、分组摊开显示，不要藏在菜单里"；"日志和工具直接从界面上拿掉"；
# 追加："4 个菜单按键做得精致一点"（选中高亮）；"样式小一点"（紧凑小尺寸）；
# "节点信息（节点卡片列表）放在上面，样式紧凑缩小些"（节点列表移到仪表盘上方，
# 节点卡片紧凑）；"节点名显示一行，不要换行分成两排（长名字用省略号）"。
# 补丁改 bridge/patch_start_button_bottom.py（幂等，可重复跑）。
echo ">>> [start-button-bottom] 启动键到底部 + 底部导航 + 节点列表置顶"
if [ -f "$CC_BRIDGE/patch_start_button_bottom.py" ]; then
  if python3 "$CC_BRIDGE/patch_start_button_bottom.py"; then
    echo ">>> [start-button-bottom] patch_start_button_bottom.py OK"
  else
    echo "ERROR: $CC_BRIDGE/patch_start_button_bottom.py 执行失败"
    exit 1
  fi
else
  echo ">>> [start-button-bottom] 警告: patch_start_button_bottom.py 不存在，跳过"
fi


# ---- 启动崩溃修复（#109 NB4A Crash）----
# 根因：patch_start_button_bottom.py 把 StatsBar 仪表盘绑定改成
# (context as MainActivity).findViewById，但 MainActivity.onCreate 在
# setContentView 之前就调用 binding.stats.setOnClickListener，此时
# Activity.findViewById 找不到任何 view -> lateinit NPE -> 启动即崩溃。
# 修复：改用 rootView.findViewById（inflate 后的 binding.root 树），
# 与 setContentView 调用顺序无关。
# 补丁改 bridge/patch_crash_fix.py（幂等，可重复跑）。
echo ">>> [crash-fix] StatsBar rootView 绑定修复"
if [ -f "$CC_BRIDGE/patch_crash_fix.py" ]; then
  if python3 "$CC_BRIDGE/patch_crash_fix.py"; then
    echo ">>> [crash-fix] patch_crash_fix.py OK"
  else
    echo "ERROR: $CC_BRIDGE/patch_crash_fix.py 执行失败"
    exit 1
  fi
else
  echo ">>> [crash-fix] 警告: patch_crash_fix.py 不存在，跳过"
fi

# ---- #111 UI 调整：菜单键拿掉、卡片改回黑色、启动键缩小单独放、抽屉删掉、
#      搜索图标删掉、顶栏紫蓝渐变、卡片宽度收窄 ----
# 用户要求（2026-10-06）："菜单取消显示，透明磨砂还是还回黑色，启动按键做小点
# 不要跟配置路由分组设置同在一行" + "侧边抽屉导航整个删掉" + "顶部工具栏搜索
# 图标删掉，工具栏背景改紫蓝渐变" + "仪表盘卡片宽度收窄"。
# 补丁改 bridge/patch_ui_tweak.py（幂等，可重复跑）。
if [ -f "$CC_BRIDGE/patch_ui_tweak.py" ]; then
  if python3 "$CC_BRIDGE/patch_ui_tweak.py"; then
    echo ">>> [ui-tweak] patch_ui_tweak.py OK"
  else
    echo "ERROR: $CC_BRIDGE/patch_ui_tweak.py 执行失败"
    exit 1
  fi
else
  echo ">>> [ui-tweak] 警告: patch_ui_tweak.py 不存在，跳过"
fi

# ---- #113 紧凑化：底部导航图标放大、仪表盘卡片纵向收紧 ----
# 用户要求（2026-10-06）："最下面4的图标需要增大，太小了" + "中间那几张卡片
# （下载/上传、自动选择、节点配置）再缩小紧凑些，纵向空间不够"。
# 补丁改 bridge/patch_compact.py（幂等，可重复跑）。
if [ -f "$CC_BRIDGE/patch_compact.py" ]; then
  if python3 "$CC_BRIDGE/patch_compact.py"; then
    echo ">>> [compact] patch_compact.py OK"
  else
    echo "ERROR: $CC_BRIDGE/patch_compact.py 执行失败"
    exit 1
  fi
else
  echo ">>> [compact] 警告: patch_compact.py 不存在，跳过"
fi

# ---- #114 底部导航图标二次放大 ----
# 用户要求（2026-10-06）："还是小" —— #113 已从 20dp 放大到 28dp，用户仍嫌小，
# 再放大到 36dp（pill 64x44dp、label 11sp 同步）。
# 补丁改 bridge/patch_nav_icons_v2.py（幂等，可重复跑）。
if [ -f "$CC_BRIDGE/patch_nav_icons_v2.py" ]; then
  if python3 "$CC_BRIDGE/patch_nav_icons_v2.py"; then
    echo ">>> [nav-icons-v2] patch_nav_icons_v2.py OK"
  else
    echo "ERROR: $CC_BRIDGE/patch_nav_icons_v2.py 执行失败"
    exit 1
  fi
else
  echo ">>> [nav-icons-v2] 警告: patch_nav_icons_v2.py 不存在，跳过"
fi

# ---- 延迟测试 VPN 守卫（2026-10-07）----
# 问题：VPN 连接时点节点列表"延迟测试"，每个节点的临时测试实例的 socket
# 可能未被 TUN 保护，测试流量被主隧道吸走（"用当前节点测所有节点"），
# 导致全部节点显示"超时"误报，但 VPN 本身工作正常。
# 方案（产品化的 workaround）：在 ConfigurationFragment.urlTest() 入口检查
# VPN 状态，运行时弹对话框让用户选择：[断开并测试] [仍要测试] [取消]。
# 补丁改 bridge/patch_urltest_vpn_guard.py（幂等，可重复跑）。
# [diag/sock-protect] 诊断分支禁用 urltest-vpn-guard：
# 1) #122 真机启动即崩，守卫补丁是除诊断日志外唯一与 #119 的差异，疑为崩溃源；
# 2) 诊断包应为 #119 代码 + 诊断日志，对话框会干扰复现步骤。
# 主分支 main 的守卫不受影响。
echo ">>> [urltest-vpn-guard] 诊断分支跳过（diag/sock-protect 专用）"

# ---- socket 保护诊断日志（2026-10-07，诊断分支 diag/sock-protect 专用）----
# 目标：定位 VPN 连接时延迟测试 socket 保护失效的具体断点。
# 只加日志、零行为变更。日志前缀统一为 SockProtectDiag，方便 logcat 过滤。
# 补丁：bridge/patch_sockprotect_diag.py（幂等，可重复跑）。
echo ">>> [sockprotect-diag] socket 保护诊断日志"
SPD_BRIDGE="../chanbox-assets/bridge"
if [ -f "$SPD_BRIDGE/patch_sockprotect_diag.py" ]; then
  if python3 "$SPD_BRIDGE/patch_sockprotect_diag.py"; then
    echo ">>> [sockprotect-diag] patch_sockprotect_diag.py OK"
  else
    echo "ERROR: $SPD_BRIDGE/patch_sockprotect_diag.py 执行失败"
    exit 1
  fi
else
  echo ">>> [sockprotect-diag] 警告: patch_sockprotect_diag.py 不存在，跳过"
fi
