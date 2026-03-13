import Foundation
import HealthKit

struct HealthSummary: Sendable {
    let averageSleepHours: Double?
    let averageHRVMilliseconds: Double?
    let windowDays: Int
}

enum HealthKitServiceError: LocalizedError {
    case unavailable
    case missingType
    case authorizationDenied

    var errorDescription: String? {
        switch self {
        case .unavailable:
            return "Health data is not available on this device."
        case .missingType:
            return "The required HealthKit data types are not available."
        case .authorizationDenied:
            return "HealthKit access was denied."
        }
    }
}

final class HealthKitService {
    private let store = HKHealthStore()
    private let windowDays = 7

    func requestAuthorization() async throws {
        guard HKHealthStore.isHealthDataAvailable() else {
            throw HealthKitServiceError.unavailable
        }

        guard let sleepType = HKObjectType.categoryType(forIdentifier: .sleepAnalysis),
              let hrvType = HKObjectType.quantityType(forIdentifier: .heartRateVariabilitySDNN) else {
            throw HealthKitServiceError.missingType
        }

        let readTypes: Set<HKObjectType> = [sleepType, hrvType]

        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            store.requestAuthorization(toShare: nil, read: readTypes) { success, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }

                if success {
                    continuation.resume()
                } else {
                    continuation.resume(throwing: HealthKitServiceError.authorizationDenied)
                }
            }
        }
    }

    func fetchLast7DaySummary() async throws -> HealthSummary {
        guard let sleepType = HKObjectType.categoryType(forIdentifier: .sleepAnalysis),
              let hrvType = HKObjectType.quantityType(forIdentifier: .heartRateVariabilitySDNN) else {
            throw HealthKitServiceError.missingType
        }

        let endDate = Date()
        let startDate = Calendar.current.date(byAdding: .day, value: -windowDays, to: endDate) ?? endDate

        async let sleepHours = fetchAverageSleepHours(type: sleepType, startDate: startDate, endDate: endDate)
        async let hrv = fetchAverageHRV(type: hrvType, startDate: startDate, endDate: endDate)

        return try await HealthSummary(
            averageSleepHours: sleepHours,
            averageHRVMilliseconds: hrv,
            windowDays: windowDays
        )
    }

    private func fetchAverageSleepHours(
        type: HKCategoryType,
        startDate: Date,
        endDate: Date
    ) async throws -> Double? {
        let predicate = HKQuery.predicateForSamples(withStart: startDate, end: endDate, options: .strictStartDate)
        let samples = try await fetchCategorySamples(type: type, predicate: predicate)

        let asleepDurations = samples.reduce(into: 0.0) { total, sample in
            guard isAsleep(sample) else {
                return
            }

            total += sample.endDate.timeIntervalSince(sample.startDate)
        }

        guard asleepDurations > 0 else {
            return nil
        }

        return asleepDurations / 3600 / Double(windowDays)
    }

    private func fetchAverageHRV(
        type: HKQuantityType,
        startDate: Date,
        endDate: Date
    ) async throws -> Double? {
        let predicate = HKQuery.predicateForSamples(withStart: startDate, end: endDate, options: .strictStartDate)
        let samples = try await fetchQuantitySamples(type: type, predicate: predicate)

        guard !samples.isEmpty else {
            return nil
        }

        let unit = HKUnit.secondUnit(with: .milli)
        let total = samples.reduce(into: 0.0) { result, sample in
            result += sample.quantity.doubleValue(for: unit)
        }

        return total / Double(samples.count)
    }

    private func fetchCategorySamples(
        type: HKCategoryType,
        predicate: NSPredicate
    ) async throws -> [HKCategorySample] {
        try await withCheckedThrowingContinuation { continuation in
            let sortDescriptors = [NSSortDescriptor(key: HKSampleSortIdentifierEndDate, ascending: false)]
            let query = HKSampleQuery(
                sampleType: type,
                predicate: predicate,
                limit: HKObjectQueryNoLimit,
                sortDescriptors: sortDescriptors
            ) { _, samples, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }

                continuation.resume(returning: samples as? [HKCategorySample] ?? [])
            }

            store.execute(query)
        }
    }

    private func fetchQuantitySamples(
        type: HKQuantityType,
        predicate: NSPredicate
    ) async throws -> [HKQuantitySample] {
        try await withCheckedThrowingContinuation { continuation in
            let sortDescriptors = [NSSortDescriptor(key: HKSampleSortIdentifierEndDate, ascending: false)]
            let query = HKSampleQuery(
                sampleType: type,
                predicate: predicate,
                limit: HKObjectQueryNoLimit,
                sortDescriptors: sortDescriptors
            ) { _, samples, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }

                continuation.resume(returning: samples as? [HKQuantitySample] ?? [])
            }

            store.execute(query)
        }
    }

    private func isAsleep(_ sample: HKCategorySample) -> Bool {
        sample.value == HKCategoryValueSleepAnalysis.asleepUnspecified.rawValue
            || sample.value == HKCategoryValueSleepAnalysis.asleepCore.rawValue
            || sample.value == HKCategoryValueSleepAnalysis.asleepDeep.rawValue
            || sample.value == HKCategoryValueSleepAnalysis.asleepREM.rawValue
    }
}
