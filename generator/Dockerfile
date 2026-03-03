FROM quay.io/performancecopilot/pcp:latest

RUN pip install git+https://github.com/tallpsmith/pmlogsynth

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
