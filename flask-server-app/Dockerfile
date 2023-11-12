FROM python:3.9-slim


# Set work directory
WORKDIR /app

# Copy requirements.txt
COPY requirements.txt /app/

# Install Requirements
RUN apt update && apt install -y wget && \
    wget https://mirror.openshift.com/pub/openshift-v4/x86_64/clients/ocp/stable/openshift-client-linux.tar.gz && \
    tar -xvf openshift-client-linux.tar.gz && \
    mv oc /usr/local/bin && \
    mv kubectl /usr/local/bin && \
    rm -rf openshift-client-linux.tar.gz && \
    pip install -r requirements.txt

# Copy code
COPY . /app/

CMD gunicorn --workers 10 --bind 0.0.0.0:5000 --log-level DEBUG main:app

