FROM openfga/openfga:v1.22.1 AS openfga

FROM alpine:3.21.3
COPY --from=openfga /openfga /openfga
USER 10001:10001
ENTRYPOINT ["/openfga"]
CMD ["run"]
