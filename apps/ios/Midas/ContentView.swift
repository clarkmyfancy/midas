import SwiftUI

struct ContentView: View {
    private enum AuthMode: String, CaseIterable, Identifiable {
        case login = "Sign In"
        case register = "Create Account"

        var id: String { rawValue }
    }

    private let authService = AuthService()
    private let healthKitService = HealthKitService()
    private let reflectionSyncService = ReflectionSyncService()

    @State private var capabilityMap: [String: Bool] = [
        "advanced_analytics": false,
        "weekly_reflection": false,
    ]
    @State private var authMode: AuthMode = .login
    @State private var authSession: AuthSession?
    @State private var email = ""
    @State private var password = ""
    @State private var authStatus = "Sign in to sync reflections with the API."
    @State private var isAuthenticating = false
    @State private var journalEntry = "I want to understand how my recovery and nervous system are aligning with how I felt this week."
    @State private var healthSummary: HealthSummary?
    @State private var reflectionSummary = ""
    @State private var syncStatus = "Health data not synced yet."
    @State private var isSyncingReflection = false
    @State private var showingPaywall = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    Text("Midas")
                        .font(.largeTitle.bold())
                    Text("A private reflection system across iPhone, web, and API.")
                        .font(.title3)
                        .foregroundStyle(.secondary)
                    Text("This starter app is ready for HealthKit, App Intents, and conversational journaling flows.")
                        .font(.body)

                    VStack(alignment: .leading, spacing: 14) {
                        Text("Account")
                            .font(.headline)

                        Picker("Account mode", selection: $authMode) {
                            ForEach(AuthMode.allCases) { mode in
                                Text(mode.rawValue).tag(mode)
                            }
                        }
                        .pickerStyle(.segmented)

                        TextField("you@example.com", text: $email)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                            .textFieldStyle(.roundedBorder)

                        SecureField("Password", text: $password)
                            .textFieldStyle(.roundedBorder)

                        Button {
                            Task {
                                await authenticate()
                            }
                        } label: {
                            HStack {
                                if isAuthenticating {
                                    ProgressView()
                                        .tint(.white)
                                }
                                Text(isAuthenticating ? "Submitting..." : authMode.rawValue)
                            }
                            .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.borderedProminent)
                        .disabled(isAuthenticating || email.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || password.count < 8)

                        if let authSession {
                            HStack {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(authSession.user.email)
                                        .font(.subheadline.weight(.semibold))
                                    Text(authSession.user.isPro ? "Pro account" : "Core account")
                                        .font(.footnote)
                                        .foregroundStyle(.secondary)
                                }

                                Spacer()

                                Button("Log Out") {
                                    logout()
                                }
                            }
                        }

                        Text(authStatus)
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding()
                    .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 24))

                    VStack(alignment: .leading, spacing: 14) {
                        Text("HealthKit Sync")
                            .font(.headline)
                        Text("Authorize sleep and HRV, summarize the last 7 days, and send that payload to the reflection API.")
                            .foregroundStyle(.secondary)
                        TextEditor(text: $journalEntry)
                            .frame(minHeight: 110)
                            .padding(10)
                            .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 16))

                        Button {
                            Task {
                                await syncReflection()
                            }
                        } label: {
                            HStack {
                                if isSyncingReflection {
                                    ProgressView()
                                        .tint(.white)
                                }
                                Text(isSyncingReflection ? "Syncing..." : "Sync Last 7 Days")
                            }
                            .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.borderedProminent)
                        .disabled(isSyncingReflection || authSession == nil)

                        Text(syncStatus)
                            .font(.footnote)
                            .foregroundStyle(.secondary)

                        if let healthSummary {
                            VStack(alignment: .leading, spacing: 8) {
                                Text("Latest Health Snapshot")
                                    .font(.subheadline.weight(.semibold))
                                Text("Average sleep: \(formattedSleepHours(healthSummary.averageSleepHours))")
                                Text("Average HRV: \(formattedHRV(healthSummary.averageHRVMilliseconds))")
                            }
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                        }

                        if !reflectionSummary.isEmpty {
                            VStack(alignment: .leading, spacing: 8) {
                                Text("Reflection Stream")
                                    .font(.subheadline.weight(.semibold))
                                Text(reflectionSummary)
                                    .foregroundStyle(.secondary)
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding()
                            .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 20))
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding()
                    .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 24))

                    VStack(alignment: .leading, spacing: 12) {
                        Text("Weekly Reflection")
                            .font(.headline)
                        Text("A core weekly summary based on your recent journals, goals, biometrics, and clarifications.")
                            .foregroundStyle(.secondary)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding()
                    .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 20))

                    withProGate(capabilityEnabled: capabilityMap["advanced_analytics"] ?? false) {
                        showingPaywall = true
                    } content: {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("Advanced Analytics")
                                .font(.headline)
                            Text("Longitudinal pattern mining, graph interpretation, and deeper analytics over the same stored data.")
                                .foregroundStyle(.secondary)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding()
                        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 20))
                    }
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
                .padding(24)
                .navigationTitle("Home")
            }
        }
        .sheet(isPresented: $showingPaywall) {
            NavigationStack {
                VStack(alignment: .leading, spacing: 16) {
                    Text("Upgrade to Midas Pro")
                        .font(.largeTitle.bold())
                    Text("Unlock deep reflection agents, advanced analytics, and cross-device memory.")
                        .foregroundStyle(.secondary)
                    Spacer()
                }
                .padding(24)
                .navigationTitle("Paywall")
            }
        }
        .task {
            await restoreSession()
        }
        .task(id: authSession?.user.id) {
            await loadCapabilities()
        }
    }

    @MainActor
    private func restoreSession() async {
        authSession = await authService.restoreSession()
        if let authSession {
            authStatus = "Signed in as \(authSession.user.email)."
            email = authSession.user.email
        } else {
            authStatus = "Sign in to sync reflections with the API."
        }
    }

    @MainActor
    private func authenticate() async {
        isAuthenticating = true
        defer { isAuthenticating = false }

        do {
            let normalizedEmail = email.trimmingCharacters(in: .whitespacesAndNewlines)
            let session = try await {
                switch authMode {
                case .login:
                    return try await authService.login(email: normalizedEmail, password: password)
                case .register:
                    return try await authService.register(email: normalizedEmail, password: password)
                }
            }()
            authSession = session
            authStatus = "Signed in as \(session.user.email)."
            await loadCapabilities()
        } catch {
            authStatus = error.localizedDescription
        }
    }

    private func loadCapabilities() async {
        guard let currentSession = authSession else {
            await MainActor.run {
                capabilityMap = [
                    "advanced_analytics": false,
                    "weekly_reflection": false,
                ]
            }
            return
        }

        guard let url = URL(string: "\(apiBaseURL)/v1/capabilities") else {
            return
        }

        do {
            var request = URLRequest(url: url)
            request.setValue("Bearer \(currentSession.accessToken)", forHTTPHeaderField: "Authorization")
            let (data, response) = try await URLSession.shared.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
                if let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 401 {
                    let restoredSession = await authService.restoreSession()
                    await MainActor.run {
                        authSession = restoredSession
                        if restoredSession == nil {
                            logoutLocally(status: "Your session expired. Sign in again.")
                        }
                    }
                }
                return
            }

            let decoded = try JSONDecoder().decode(CapabilityMapResponse.self, from: data)
            await MainActor.run {
                capabilityMap = decoded.capabilities
            }
        } catch {
            #if DEBUG
            print("Failed to load capabilities: \(error)")
            #endif
        }
    }

    private var apiBaseURL: String {
        if let configuredBaseURL = Bundle.main.object(forInfoDictionaryKey: "MIDAS_API_BASE_URL") as? String,
           !configuredBaseURL.isEmpty {
            return configuredBaseURL
        }

        return "http://localhost:8000"
    }

    @MainActor
    private func syncReflection() async {
        guard let authSession else {
            syncStatus = "Sign in before syncing reflections."
            return
        }

        isSyncingReflection = true
        syncStatus = "Requesting HealthKit access..."
        reflectionSummary = ""
        var healthSnapshot: HealthSummary?

        do {
            try await healthKitService.requestAuthorization()
            syncStatus = "Fetching the last 7 days of sleep and HRV..."
            let summary = try await healthKitService.fetchLast7DaySummary()
            healthSummary = summary
            healthSnapshot = summary

            syncStatus = "Streaming reflection from the backend..."
            reflectionSummary = try await reflectionSyncService.streamReflection(
                accessToken: authSession.accessToken,
                journalEntry: journalEntry,
                goals: [],
                healthSummary: summary
            )
            syncStatus = "Synced the last 7 days of HealthKit sleep and HRV."
        } catch {
            if case ReflectionSyncServiceError.unexpectedStatusCode(401) = error,
               let summary = healthSnapshot,
               let restoredSession = await authService.restoreSession() {
                self.authSession = restoredSession
                do {
                    reflectionSummary = try await reflectionSyncService.streamReflection(
                        accessToken: restoredSession.accessToken,
                        journalEntry: journalEntry,
                        goals: [],
                        healthSummary: summary
                    )
                    syncStatus = "Synced the last 7 days of HealthKit sleep and HRV."
                    isSyncingReflection = false
                    return
                } catch {
                    syncStatus = error.localizedDescription
                }
            } else {
                syncStatus = error.localizedDescription
            }
        }

        isSyncingReflection = false
    }

    @MainActor
    private func logout() {
        let currentSession = authSession
        Task {
            await authService.logout(currentSession: currentSession)
        }
        logoutLocally(status: "Signed out.")
    }

    @MainActor
    private func logoutLocally(status: String) {
        authSession = nil
        capabilityMap = [
            "advanced_analytics": false,
            "weekly_reflection": false,
        ]
        reflectionSummary = ""
        healthSummary = nil
        syncStatus = "Health data not synced yet."
        authStatus = status
    }

    private func formattedSleepHours(_ hours: Double?) -> String {
        guard let hours else {
            return "Unavailable"
        }

        return String(format: "%.1f hours/night", hours)
    }

    private func formattedHRV(_ hrv: Double?) -> String {
        guard let hrv else {
            return "Unavailable"
        }

        return String(format: "%.0f ms", hrv)
    }
}

private struct CapabilityMapResponse: Decodable {
    let capabilities: [String: Bool]
}
