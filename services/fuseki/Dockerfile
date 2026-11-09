# Apache Jena Fuseki (the release jar from Maven Central, checked by its checksum) on a Java 21 runtime.
# Apache publishes no Fuseki image; this is the smallest one we can build ourselves. To update: change the version
# and the checksum (sha256 of jena-fuseki-server-<version>.jar), rebuild, run the endpoint check of the workspace.
FROM eclipse-temurin:21-jre-noble

ARG FUSEKI_VERSION=6.2.0
ADD --checksum=sha256:2c92c598e65ab69d99820052e05f4277ed1d77980a8845f87545ad35b71a76ee \
    https://repo1.maven.org/maven2/org/apache/jena/jena-fuseki-server/${FUSEKI_VERSION}/jena-fuseki-server-${FUSEKI_VERSION}.jar \
    /opt/fuseki/fuseki-server.jar

# a fixed user id, so the database directory on the host can be owned by it (host/install.sh)
RUN groupadd --gid 9030 fuseki && useradd --uid 9030 --gid fuseki --no-create-home --shell /usr/sbin/nologin fuseki \
 && chmod 644 /opt/fuseki/fuseki-server.jar && mkdir -p /fuseki/database && chown fuseki:fuseki /fuseki/database
USER fuseki
WORKDIR /fuseki
ENV JAVA_OPTS="-Xmx4g"
EXPOSE 3030
# the arguments of the service: --conf … (public, read-only) or --update --loc … (loader); see ../compose.yml
ENTRYPOINT ["sh", "-c", "exec java $JAVA_OPTS -cp /opt/fuseki/fuseki-server.jar org.apache.jena.fuseki.main.cmds.FusekiMainCmd \"$@\"", "fuseki"]
