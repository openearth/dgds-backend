FROM continuumio/miniconda3
COPY environment.yml /tmp/environment.yml
RUN conda env create -f /tmp/environment.yml

# Pull the environment name out of the environment.yml
RUN echo "source activate $(head -1 /tmp/environment.yml | cut -d' ' -f2)" > ~/.bashrc
ENV PATH /opt/conda/envs/$(head -1 /tmp/environment.yml | cut -d' ' -f2)/bin:$PATH

COPY glossis.py /root/glossis.py
# ENTRYPOINT ["python", "~/glossis.py"]
# CMD ["-h"]
