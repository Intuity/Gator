FROM ubuntu:22.04
SHELL ["/bin/bash", "-c"]
ENV SHELL=/bin/bash
ENV TZ=Europe/London

# Manually set timezone
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Force shell to use bash
RUN rm /bin/sh && ln -s /bin/bash /bin/sh

# Update aptitude
RUN export DEBIAN_FRONTEND=noninteractive && \
    apt update -y && \
    apt upgrade -y && \
    apt install -y software-properties-common

# Install Python3.11
RUN export DEBIAN_FRONTEND=noninteractive && \
    add-apt-repository -y ppa:deadsnakes/ppa && \
    apt update -y && \
    apt install -y \
        python3.11 \
        python3.11-venv \
        python3.11-distutils \
        python3.11-dev \
        python3-pip
RUN rm /usr/bin/python3 && \
    ln -s $(which python3.11) /usr/bin/python3
RUN rm -f /usr/bin/python && \
    ln -s $(which python3.11) /usr/bin/python
RUN python3 -m pip install poetry poethepoet
RUN python3 -m pip install cmake==3.24

# Install NodeJS
ENV NVM_DIR=/usr/local/nvm
ENV NODE_VERSION=22
RUN export DEBIAN_FRONTEND=noninteractive && \
    apt install -y curl
RUN mkdir -p $NVM_DIR
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh | bash
RUN source $NVM_DIR/nvm.sh && \
    nvm install $NODE_VERSION && \
    nvm alias default $NODE_VERSION && \
    nvm use default

ENV NODE_PATH=$NVM_DIR/v$NODE_VERSION/lib/node_modules
ENV PATH=$NVM_DIR/v$NODE_VERSION/bin:$PATH

# Copy the whole of Gator into the container
COPY . /root/gator

# Install poetry and python dependencies
RUN python3.11 -m pip install poetry poethepoet
RUN cd /root/gator && poetry lock && poetry install

# Install npm dependencies and then build the frontend
RUN source $NVM_DIR/nvm.sh && \
    cd /root/gator/gator-hub && \
    npm install && \
    npm run build

# Launch Gator
ENV GATOR_HUB_ROOT=/root/gator/gator-hub/dist
WORKDIR /root/gator
ENTRYPOINT ["poetry", "run", "python3.11", "-m", "gator.hub"]
CMD ["--host", "0.0.0.0", "--port", "8080", "--db-host", "127.0.0.1", "--db-port", "5432"]
