# About

This contains the config of wireguard user interface. 
We use wg-ui-auto-user that allows us to create tunnels without accounts (which is generally a stupid idea). 
Particularly we use the wg-ui api for tunnel management.

# Dependencies

We mainly run it inside docker: 
- docker.io
- docker-compose

More info in the repositories readme. 

# Configuration

Is done in the docker-compose.yml file

# Building and running

We have two convenience scripts:

- build.sh to build a new docker container. 
- start.sh to start it using docker-compose using the yml file.

# Credits

- wg-ui: https://github.com/EmbarkStudios/wg-ui
- wg-ui-auto-user: https://git.aperture-labs.org/AS59645/wg-ui-auto-user
- https://doing-stupid-things.as59645.net/payload/is/just/packet/overhead/2022/10/02/making-it-ping-when-it-shouldnt-part-1.html
