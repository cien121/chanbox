
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
