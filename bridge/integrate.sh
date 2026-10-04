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

echo ">>> [sing-box-lx] 全部完成"
