FROM eclipse-temurin:25-jdk-alpine AS builder
WORKDIR /build
COPY src/StatusServer.java .
RUN javac --release 17 -d out StatusServer.java

FROM eclipse-temurin:25-jre-alpine
RUN addgroup -g 10001 app && adduser -D -u 10001 -G app app
WORKDIR /app
COPY --from=builder /build/out ./
USER 10001:10001
EXPOSE 8001
CMD ["java", "--add-modules", "jdk.httpserver", "-cp", "/app", "StatusServer"]
