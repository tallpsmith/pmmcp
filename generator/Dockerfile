FROM quay.io/performancecopilot/pcp:latest

RUN dnf install -y python3-pip git && dnf clean all
RUN pip3 install git+https://github.com/tallpsmith/pmlogsynth

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
