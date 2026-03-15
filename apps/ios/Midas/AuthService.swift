import Foundation
import Security

struct AuthUser: Codable, Sendable {
    let id: String
    let email: String
    let isPro: Bool

    private enum CodingKeys: String, CodingKey {
        case id
        case email
        case isPro = "is_pro"
    }
}

struct AuthSession: Codable, Sendable {
    let accessToken: String
    let refreshToken: String
    let user: AuthUser

    private enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case user
    }
}

private struct AuthRequest: Encodable {
    let email: String
    let password: String
}

private struct RefreshRequest: Encodable {
    let refresh_token: String
}

private struct StoredRefreshToken: Codable {
    let refreshToken: String
}

private struct LogoutResponse: Decodable {
    let ok: Bool
}

enum AuthServiceError: LocalizedError {
    case invalidURL
    case invalidResponse
    case unexpectedStatusCode(Int, String)
    case encodingFailed

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "The auth API URL is invalid."
        case .invalidResponse:
            return "The auth API returned an invalid response."
        case let .unexpectedStatusCode(statusCode, detail):
            return detail.isEmpty ? "The auth API returned status \(statusCode)." : detail
        case .encodingFailed:
            return "The auth request could not be encoded."
        }
    }
}

final class AuthService {
    private let session: URLSession
    private let encoder = JSONEncoder()
    private let decoder = JSONDecoder()
    private let apiBaseURL: String
    private let keychainAccount = "midas.mobile.refresh-token"
    private let keychainService = "com.clarkmyfancy.midas"

    init(
        session: URLSession = .shared,
        apiBaseURL: String = Bundle.main.object(forInfoDictionaryKey: "MIDAS_API_BASE_URL") as? String ?? "http://localhost:8000"
    ) {
        self.session = session
        self.apiBaseURL = apiBaseURL
    }

    func restoreSession() async -> AuthSession? {
        guard let refreshToken = loadStoredRefreshToken() else {
            return nil
        }

        do {
            return try await refresh(refreshToken: refreshToken)
        } catch {
            clearStoredRefreshToken()
            return nil
        }
    }

    func login(email: String, password: String) async throws -> AuthSession {
        try await authenticate(path: "v1/auth/login", email: email, password: password)
    }

    func register(email: String, password: String) async throws -> AuthSession {
        try await authenticate(path: "v1/auth/register", email: email, password: password)
    }

    func refresh(refreshToken: String) async throws -> AuthSession {
        let authSession = try await requestSession(
            path: "v1/auth/refresh",
            payload: RefreshRequest(refresh_token: refreshToken)
        )
        saveRefreshToken(authSession.refreshToken)
        return authSession
    }

    func logout(currentSession: AuthSession?) async {
        let refreshToken = currentSession?.refreshToken ?? loadStoredRefreshToken()
        defer {
            clearStoredRefreshToken()
        }

        guard let refreshToken else {
            return
        }

        _ = try? await request(
            path: "v1/auth/logout",
            method: "POST",
            payload: RefreshRequest(refresh_token: refreshToken)
        ) as LogoutResponse
    }

    private func authenticate(path: String, email: String, password: String) async throws -> AuthSession {
        let authSession = try await requestSession(
            path: path,
            payload: AuthRequest(email: email, password: password)
        )
        saveRefreshToken(authSession.refreshToken)
        return authSession
    }

    private func requestSession<Payload: Encodable>(
        path: String,
        payload: Payload
    ) async throws -> AuthSession {
        try await request(path: path, method: "POST", payload: payload)
    }

    private func request<ResponseType: Decodable, Payload: Encodable>(
        path: String,
        method: String,
        payload: Payload
    ) async throws -> ResponseType {
        guard let url = URL(string: apiBaseURL)?.appending(path: path) else {
            throw AuthServiceError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("application/json", forHTTPHeaderField: "Accept")

        do {
            request.httpBody = try encoder.encode(payload)
        } catch {
            throw AuthServiceError.encodingFailed
        }

        let (data, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw AuthServiceError.invalidResponse
        }

        guard httpResponse.statusCode == 200 else {
            throw AuthServiceError.unexpectedStatusCode(
                httpResponse.statusCode,
                detail(from: data)
            )
        }

        return try decoder.decode(ResponseType.self, from: data)
    }

    private func loadStoredRefreshToken() -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: keychainService,
            kSecAttrAccount as String: keychainAccount,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]

        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        guard status == errSecSuccess, let data = item as? Data else {
            return nil
        }

        return (try? decoder.decode(StoredRefreshToken.self, from: data))?.refreshToken
    }

    private func saveRefreshToken(_ refreshToken: String) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: keychainService,
            kSecAttrAccount as String: keychainAccount,
        ]
        let payload = StoredRefreshToken(refreshToken: refreshToken)
        let data = (try? encoder.encode(payload)) ?? Data()

        SecItemDelete(query as CFDictionary)
        let attributes: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: keychainService,
            kSecAttrAccount as String: keychainAccount,
            kSecValueData as String: data,
        ]
        SecItemAdd(attributes as CFDictionary, nil)
    }

    private func clearStoredRefreshToken() {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: keychainService,
            kSecAttrAccount as String: keychainAccount,
        ]
        SecItemDelete(query as CFDictionary)
    }

    private func detail(from data: Data) -> String {
        guard
            let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else {
            return String(data: data, encoding: .utf8) ?? ""
        }

        return (object["detail"] as? String) ?? (object["message"] as? String) ?? ""
    }
}
