FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . .

RUN chmod +x build.sh

RUN ./build.sh

EXPOSE 4444

CMD ["./app-bin"]