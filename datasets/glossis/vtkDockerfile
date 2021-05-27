FROM continuumio/miniconda3

RUN \
    apt-get update --fix-missing && \
    apt-get install -y libglu1-mesa-dev && \
  rm -rf /var/lib/apt/lists/*

COPY vtk_environment.yml /tmp/environment.yml
RUN conda env create -f /tmp/environment.yml

RUN echo "source activate env" > /root/.bashrc
ENV PATH=/opt/gcloud/google-cloud-sdk/bin:/opt/conda/envs/env/bin:$PATH 

RUN mkdir /opt/gcloud /opt/datasets
RUN (cd /opt/gcloud && curl -O https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-sdk-337.0.0-linux-x86_64.tar.gz && tar -xzf google-cloud-sdk-337.0.0-linux-x86_64.tar.gz)
RUN /opt/gcloud/google-cloud-sdk/install.sh --disable-installation-options

# TODO move to subdirectory
COPY *.py /root/
ENTRYPOINT ["bash", "-c"]
CMD ["python /root/glossis.py"]
