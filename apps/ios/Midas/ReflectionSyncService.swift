import Foundation

struct ReflectionPayload: Encodable {
    let journal_entry: String
    let goals: [String]
    let sleep_hours: Double?
    let hrv_ms: Double?
}

enum ReflectionSyncServiceError: LocalizedError {
    case invalidURL
    case invalidResponse
    case unexpectedStatusCode(Int)

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "The reflection API URL is invalid."
        case .invalidResponse:
            return "The reflection API returned an invalid response."
        case let .unexpectedStatusCode(statusCode):
            return "The reflection API returned status \(statusCode)."
        }
    }
}

final class ReflectionSyncService {
    private let session: URLSession
    private let encoder = JSONEncoder()
    private let apiBaseURL: String

    init(
        session: URLSession = .shared,
        apiBaseURL: String = Bundle.main.object(forInfoDictionaryKey: "MIDAS_API_BASE_URL") as? String ?? "http://localhost:8000"
    ) {
        self.session = session
        self.apiBaseURL = apiBaseURL
    }

    func streamReflection(
        accessToken: String,
        journalEntry: String,
        goals: [String],
        healthSummary: HealthSummary
    ) async throws -> String {
        guard let url = URL(string: apiBaseURL)?.appending(path: "v1/reflections") else {
            throw ReflectionSyncServiceError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("text/event-stream", forHTTPHeaderField: "Accept")
        request.httpBody = try encoder.encode(
            ReflectionPayload(
                journal_entry: journalEntry,
                goals: goals,
                sleep_hours: healthSummary.averageSleepHours,
                hrv_ms: healthSummary.averageHRVMilliseconds
            )
        )

        let (bytes, response) = try await session.bytes(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw ReflectionSyncServiceError.invalidResponse
        }

        guard httpResponse.statusCode == 200 else {
            throw ReflectionSyncServiceError.unexpectedStatusCode(httpResponse.statusCode)
        }

        var streamedSummary = ""

        for try await line in bytes.lines {
            guard line.hasPrefix("data: ") else {
                continue
            }

            streamedSummary.append(String(line.dropFirst(6)))
        }

        return streamedSummary.trimmingCharacters(in: .whitespacesAndNewlines)
    }
}
