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

echo ">>> [sing-box-lx] 全部完成"
