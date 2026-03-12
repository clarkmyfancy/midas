import SwiftUI

struct ContentView: View {
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
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            .padding(24)
            .navigationTitle("Home")
        }
    }
}

#Preview {
    ContentView()
}

