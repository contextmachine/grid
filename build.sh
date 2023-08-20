docker buildx build --no-cache --platform linux/amd64  --tag sthv/mfb_sw_l2:test  --push .
docker run --platform linux/amd64 --rm --tty -p 7711:7711 sthv/mfb_sw_l2:test

