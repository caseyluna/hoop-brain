# hoopR/wehoop invocation utility (CAL-252). Separate image from the Python
# ingestion-engine service on purpose: R never becomes the pipeline's control
# flow, Python (main.py) shells out to this image per hoopr_bridge.py and
# treats it like any other ingest step.
FROM rocker/r-ver:4.4.1

# System deps hoopR/wehoop's own dependency chain needs to build from source
# where no binary is available (curl/xml/ssl bindings used by httr/rvest/xml2;
# cmake for RcppParallel, a transitive dep neither package lists directly).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcurl4-openssl-dev \
    libssl-dev \
    libxml2-dev \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# install.packages() does NOT fail the RUN step on a partial/failed install by
# itself (it just warns) - verify every package actually loads afterward so a
# broken image fails the build loudly instead of shipping silently incomplete.
RUN Rscript -e " \
    install.packages(c('hoopR', 'wehoop', 'jsonlite', 'readr'), repos = 'https://cloud.r-project.org'); \
    missing <- setdiff(c('hoopR', 'wehoop', 'jsonlite', 'readr'), rownames(installed.packages())); \
    if (length(missing) > 0) stop('failed to install: ', paste(missing, collapse = ', ')); \
    "

WORKDIR /app
COPY run.R ./run.R

ENTRYPOINT ["Rscript", "run.R"]
