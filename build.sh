docker buildx build --no-cache --platform linux/amd64  --tag  cr.yandex/crpfskvn79g5ht8njq0k/mfb_sw_l2:test  --push .
docker run --platform linux/amd64 --rm --tty -p 7711:7711  cr.yandex/crpfskvn79g5ht8njq0k/mfb_sw_l2:test

