import SwiftUI

struct ContentView: View {
    @State private var isWeeklyReflectionEnabled = false
    @State private var showingPaywall = false

    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 20) {
                Text("Midas")
                    .font(.largeTitle.bold())
                Text("A private reflection system across iPhone, web, and API.")
                    .font(.title3)
                    .foregroundStyle(.secondary)
                Text("This starter app is ready for HealthKit, App Intents, and conversational journaling flows.")
                    .font(.body)

                withProGate(capabilityEnabled: isWeeklyReflectionEnabled) {
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
    }
}
