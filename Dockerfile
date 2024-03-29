FROM debian:stretch-slim

RUN apt-get update  \
  && apt-get install -y --no-install-recommends \
  build-essential \
  ca-certificates \
  curl \
  fontconfig \
  gcc \
  git \
  iputils-ping \
  libbz2-dev \
  libdb5.3-dev \
  libevent-dev \
  libexpat1-dev \
  libffi-dev \
  libgdbm-dev \
  liblzma-dev \
  libncurses-dev \
  libncurses5-dev \
  libncursesw5-dev \
  libreadline-dev \
  libsqlite3-dev \
  libssl-dev \
  locales \
  make \
  procps \
  python \
  python-pip \
  python-setuptools \
  ssh \
  vim \
  wget \
  zlib1g-dev

RUN apt-get install -y --no-install-recommends \
  libssl1.0-dev

RUN git clone git://github.com/yyuu/pyenv.git ~/.pyenv --depth=20 \
    && echo 'export PATH="$HOME/.pyenv/bin:$PATH"' >> ~/.bashrc \
    && echo 'eval "$(pyenv init -)"' >> ~/.bashrc

# Speed up (optional)
# RUN cd ~/.pyenv && src/configure && make -C src || true

RUN git clone https://github.com/magicmonty/bash-git-prompt.git ~/.bash-git-prompt --depth=20 \
    && echo 'GIT_PROMPT_ONLY_IN_REPO=1' >> ~/.bashrc \
    && echo 'source ~/.bash-git-prompt/gitprompt.sh' >> ~/.bashrc

ENV PYVERS="3.7.16 3.11.1 3.10.9 3.9.16 3.8.16"

RUN for i in ${PYVERS}; do \
        ~/.pyenv/bin/pyenv install ${i}; \
        echo ${i} >> ~/.pyver-installed-okay; \
    done

RUN ~/.pyenv/bin/pyenv global $(cat ~/.pyver-installed-okay) \
    && ~/.pyenv/bin/pyenv rehash

RUN python -m pip install wheel \
    && python -m pip install tox \
    && ~/.pyenv/bin/pyenv rehash

RUN git clone https://github.com/Kintyre/ksconf.git

RUN bash
