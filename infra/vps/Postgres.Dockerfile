ARG POSTGRES_MAJOR=17
FROM postgres:${POSTGRES_MAJOR}-alpine
COPY postgres/init-runtime-role.sh /docker-entrypoint-initdb.d/10-runtime-role.sh
COPY postgres/backup.sh /opt/backup.sh
RUN sed -i 's/\r$//' /docker-entrypoint-initdb.d/10-runtime-role.sh /opt/backup.sh \
    && chmod 0755 /docker-entrypoint-initdb.d/10-runtime-role.sh /opt/backup.sh
