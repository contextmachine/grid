chmod +x upload_static.sh
./upload_static.sh
docker buildx build --platform linux/amd64  --tag  sthv/mfb_sw_l2:test  --push .
#docker build --no-cache -t  cr.yandex/crpfskvn79g5ht8njq0k/mfb_sw_l2:test .
#docker run --platform linux/amd64 --rm --tty -p 7711:7711  cr.yandex/crpfskvn79g5ht8njq0k/mfb_sw_l2:test

