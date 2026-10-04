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
echo ">>> [sing-box-lx] 完成"
