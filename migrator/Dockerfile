FROM flyway/flyway:11-alpine

COPY conf/flyway.conf /flyway/conf/flyway.conf

COPY sql /flyway/sql

CMD ["migrate"]