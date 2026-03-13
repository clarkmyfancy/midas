import SwiftUI

struct ContentView: View {
    private let healthKitService = HealthKitService()
    private let reflectionSyncService = ReflectionSyncService()

    @State private var capabilityMap: [String: Bool] = [
        "pro_analytics": false,
        "weekly_reflection": false,
        "mental_model_graph": false,
    ]
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
                        .disabled(isSyncingReflection)

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

                    withProGate(capabilityEnabled: capabilityMap["weekly_reflection"] ?? false) {
                        showingPaywall = true
                    } content: {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("Weekly Reflection")
                                .font(.headline)
                            Text("A deep weekly coaching summary based on journals, biometrics, and calendar history.")
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
            await loadCapabilities()
        }
    }

    private func loadCapabilities() async {
        guard let url = URL(string: "\(apiBaseURL)/v1/capabilities") else {
            return
        }

        do {
            let (data, response) = try await URLSession.shared.data(from: url)
            guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
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
        isSyncingReflection = true
        syncStatus = "Requesting HealthKit access..."
        reflectionSummary = ""

        do {
            try await healthKitService.requestAuthorization()
            syncStatus = "Fetching the last 7 days of sleep and HRV..."
            let summary = try await healthKitService.fetchLast7DaySummary()
            healthSummary = summary

            syncStatus = "Streaming reflection from the backend..."
            reflectionSummary = try await reflectionSyncService.streamReflection(
                journalEntry: journalEntry,
                goals: [],
                healthSummary: summary
            )
            syncStatus = "Synced the last 7 days of HealthKit sleep and HRV."
        } catch {
            syncStatus = error.localizedDescription
        }

        isSyncingReflection = false
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
