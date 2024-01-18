#!/bin/sh

if [ ! -d "./wg-ui-auto-user" ]; then
    git clone https://git.aperture-labs.org/AS59645/wg-ui-auto-user.git
fi

sed wg-ui-auto-user/Dockerfile -i -e 's|gcr.io/distroless/base|docker.io/golang:latest|'

cd wg-ui-auto-user
docker build . -t wg-ui
