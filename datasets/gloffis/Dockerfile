FROM continuumio/miniconda3
COPY environment.yml /tmp/environment.yml
RUN conda env create -f /tmp/environment.yml

# Pull the environment name out of the environment.yml
RUN echo "source activate env" > /root/.bashrc
ENV PATH /opt/conda/envs/env/bin:$PATH

COPY *.py /root/
ENTRYPOINT ["bash", "-c"]
CMD ["python /root/gloffis.py"]
