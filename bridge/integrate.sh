#!/bin/bash
# ChanBox Xray 桥接集成脚本
# 在 workflow 的 "Customize branding and theme" 之后、"Build libcore" 之前运行
# working-directory: nekobox
set -e

XRAY_VERSION="v26.3.27"

echo ">>> [xraybridge] 复制桥接代码"
mkdir -p libcore/xraybridge
cp -f ../chanbox-assets/bridge/xraybridge/bridge.go libcore/xraybridge/bridge.go

echo ">>> [xraybridge] 添加 xray-core 依赖 (version: $XRAY_VERSION)"
cd libcore
if ! grep -q "github.com/xtls/xray-core" go.mod; then
  go mod edit -require=github.com/xtls/xray-core@$XRAY_VERSION
fi

echo ">>> [xraybridge] 更新 go.sum"
go mod tidy

echo ">>> [xraybridge] 修改 build.sh 以包含 xraybridge 包"
# bind 命令末尾是 " ."（待绑定的包），改成 " . ./xraybridge"
if ! grep -q '\./xraybridge' build.sh; then
  sed -i 's| \. || exit 1| . ./xraybridge || exit 1|' build.sh
fi

echo ">>> [xraybridge] 验证 build.sh"
grep -o "gomobile-matsuri bind.*\./xraybridge" build.sh || {
  echo "ERROR: build.sh 未成功加入 ./xraybridge"
  exit 1
}

echo ">>> [xraybridge] 集成完成"
cd ..
