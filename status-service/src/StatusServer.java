import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.concurrent.Executors;

/** Read-only fixture API. No dependencies beyond the Java 17 standard library. */
public final class StatusServer {
    private static final Map<String, String> STATES = Map.of(
        "atlas", "\"status\":\"degraded\",\"message\":\"Latence de connexion élevée ; investigation en cours.\"",
        "nova", "\"status\":\"operational\",\"message\":\"Aucun incident en cours.\"",
        "orion", "\"status\":\"outage\",\"message\":\"Maintenance de l'espace finance.\"",
        "vpn", "\"status\":\"operational\",\"message\":\"Passerelle VPN disponible.\""
    );

    public static void main(String[] args) throws IOException {
        int port = Integer.parseInt(System.getenv().getOrDefault("PORT", "8001"));
        HttpServer server = HttpServer.create(new InetSocketAddress("0.0.0.0", port), 0);
        server.createContext("/", exchange -> {
            String path = exchange.getRequestURI().getPath();
            int code = 200;
            String body;
            if (!exchange.getRequestMethod().equals("GET")) {
                code = 405;
                body = "{\"detail\":\"Method not allowed\"}";
            } else if (path.equals("/health")) {
                body = "{\"status\":\"ok\"}";
            } else if (path.startsWith("/services/") && STATES.containsKey(path.substring(10))) {
                String service = path.substring(10);
                body = "{\"service_id\":\"" + service + "\"," + STATES.get(service) + "}";
            } else {
                code = 404;
                body = "{\"detail\":\"Unknown service\"}";
            }
            byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().set("Content-Type", "application/json; charset=utf-8");
            exchange.getResponseHeaders().set("X-Content-Type-Options", "nosniff");
            exchange.sendResponseHeaders(code, bytes.length);
            try (var stream = exchange.getResponseBody()) {
                stream.write(bytes);
            }
        });
        server.setExecutor(Executors.newFixedThreadPool(4));
        server.start();
        System.out.println("Fixture status API listening on " + port);
    }
}
