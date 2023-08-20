FROM ghcr.io/contextmachine/mmcore
LABEL authors="andrewastakhov"
WORKDIR /mmcore
COPY . .
EXPOSE 7711
ENV MMCORE_APPPREFIX="/cxm/api/v2/mfb_sw_l2/"
ENV MMCORE_ADDRESS="https://viewer.contextmachine.online"
RUN python3 -m pip install python-multipart --break-system-packages
ENTRYPOINT ["python3", "main.py"]
