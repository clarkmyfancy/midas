import SwiftUI

@ViewBuilder
func withProGate<Content: View>(
    capabilityEnabled: Bool,
    onUpgrade: @escaping () -> Void,
    @ViewBuilder content: () -> Content
) -> some View {
    if capabilityEnabled {
        content()
    } else {
        ZStack {
            content()
                .blur(radius: 1.5)
                .overlay {
                    RoundedRectangle(cornerRadius: 20)
                        .fill(.black.opacity(0.18))
                }

            VStack(spacing: 12) {
                Image(systemName: "lock.fill")
                    .font(.title2)
                Text("Pro Feature")
                    .font(.headline)
                Button("Upgrade to Pro", action: onUpgrade)
                    .buttonStyle(.borderedProminent)
            }
            .padding(20)
        }
    }
}

