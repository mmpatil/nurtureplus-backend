import Foundation

// MARK: - Nurture+ API Client for iOS
// Complete API reference for all 40 endpoints

// ============================================================================
// MARK: - Configuration
// ============================================================================

struct NurtureConfig {
    static let baseURL = "http://localhost:8000"  // Change to production URL
    static let timeout: TimeInterval = 30
}

// ============================================================================
// MARK: - Auth Models
// ============================================================================

struct SessionResponse: Codable {
    let userId: String
    let firebaseUid: String
    
    enum CodingKeys: String, CodingKey {
        case userId = "user_id"
        case firebaseUid = "firebase_uid"
    }
}

// ============================================================================
// MARK: - Baby Models
// ============================================================================

struct Baby: Codable, Identifiable {
    let id: UUID
    let userId: UUID
    let name: String
    let birthDate: Date
    let photoUrl: String?
    let createdAt: Date
    let updatedAt: Date
    
    enum CodingKeys: String, CodingKey {
        case id, name
        case userId = "user_id"
        case birthDate = "birth_date"
        case photoUrl = "photo_url"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}

struct BabyCreate: Codable {
    let name: String
    let birthDate: Date
    let photoUrl: String?
    
    enum CodingKeys: String, CodingKey {
        case name
        case birthDate = "birth_date"
        case photoUrl = "photo_url"
    }
}

struct BabyUpdate: Codable {
    let name: String?
    let birthDate: Date?
    let photoUrl: String?
    
    enum CodingKeys: String, CodingKey {
        case name
        case birthDate = "birth_date"
        case photoUrl = "photo_url"
    }
}

struct BabyListResponse: Codable {
    let items: [Baby]
    let total: Int
    let limit: Int
    let offset: Int
}

// ============================================================================
// MARK: - Feeding Models
// ============================================================================

struct Feeding: Codable, Identifiable {
    let id: UUID
    let babyId: UUID
    let feedingType: String  // bottle, breast_left, breast_right, both
    let amountMl: Int?
    let durationMin: Int?
    let timestamp: Date
    let notes: String?
    let createdAt: Date
    let updatedAt: Date
    
    enum CodingKeys: String, CodingKey {
        case id
        case babyId = "baby_id"
        case feedingType = "feeding_type"
        case amountMl = "amount_ml"
        case durationMin = "duration_min"
        case timestamp, notes
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}

struct FeedingCreate: Codable {
    let feedingType: String
    let amountMl: Int?
    let durationMin: Int?
    let timestamp: Date
    let notes: String?
    
    enum CodingKeys: String, CodingKey {
        case feedingType = "feeding_type"
        case amountMl = "amount_ml"
        case durationMin = "duration_min"
        case timestamp, notes
    }
}

struct FeedingUpdate: Codable {
    let feedingType: String?
    let amountMl: Int?
    let durationMin: Int?
    let timestamp: Date?
    let notes: String?
    
    enum CodingKeys: String, CodingKey {
        case feedingType = "feeding_type"
        case amountMl = "amount_ml"
        case durationMin = "duration_min"
        case timestamp, notes
    }
}

struct FeedingListResponse: Codable {
    let items: [Feeding]
    let total: Int
    let limit: Int
    let offset: Int
}

// ============================================================================
// MARK: - Diaper Models
// ============================================================================

struct Diaper: Codable, Identifiable {
    let id: UUID
    let babyId: UUID
    let diaperType: String  // wet, dirty, both, dry
    let timestamp: Date
    let notes: String?
    let createdAt: Date
    let updatedAt: Date
    
    enum CodingKeys: String, CodingKey {
        case id
        case babyId = "baby_id"
        case diaperType = "diaper_type"
        case timestamp, notes
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}

struct DiaperCreate: Codable {
    let diaperType: String
    let timestamp: Date
    let notes: String?
    
    enum CodingKeys: String, CodingKey {
        case diaperType = "diaper_type"
        case timestamp, notes
    }
}

struct DiaperUpdate: Codable {
    let diaperType: String?
    let timestamp: Date?
    let notes: String?
    
    enum CodingKeys: String, CodingKey {
        case diaperType = "diaper_type"
        case timestamp, notes
    }
}

struct DiaperListResponse: Codable {
    let items: [Diaper]
    let total: Int
    let limit: Int
    let offset: Int
}

// ============================================================================
// MARK: - Sleep Models
// ============================================================================

struct Sleep: Codable, Identifiable {
    let id: UUID
    let babyId: UUID
    let startTime: Date
    let endTime: Date?
    let durationMin: Int?
    let quality: String?  // great, good, fair, poor, etc.
    let notes: String?
    let createdAt: Date
    let updatedAt: Date
    
    enum CodingKeys: String, CodingKey {
        case id
        case babyId = "baby_id"
        case startTime = "start_time"
        case endTime = "end_time"
        case durationMin = "duration_min"
        case quality, notes
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}

struct SleepCreate: Codable {
    let startTime: Date
    let endTime: Date?
    let durationMin: Int?
    let quality: String?
    let notes: String?
    
    enum CodingKeys: String, CodingKey {
        case startTime = "start_time"
        case endTime = "end_time"
        case durationMin = "duration_min"
        case quality, notes
    }
}

struct SleepUpdate: Codable {
    let startTime: Date?
    let endTime: Date?
    let durationMin: Int?
    let quality: String?
    let notes: String?
    
    enum CodingKeys: String, CodingKey {
        case startTime = "start_time"
        case endTime = "end_time"
        case durationMin = "duration_min"
        case quality, notes
    }
}

struct SleepListResponse: Codable {
    let items: [Sleep]
    let total: Int
    let limit: Int
    let offset: Int
}

// ============================================================================
// MARK: - Mood Models
// ============================================================================

struct Mood: Codable, Identifiable {
    let id: UUID
    let babyId: UUID
    let mood: String  // happy, sad, anxious, ok, etc.
    let energy: String  // high, medium, low
    let timestamp: Date
    let notes: String?
    let createdAt: Date
    let updatedAt: Date
    
    enum CodingKeys: String, CodingKey {
        case id
        case babyId = "baby_id"
        case mood, energy, timestamp, notes
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}

struct MoodCreate: Codable {
    let mood: String
    let energy: String
    let timestamp: Date
    let notes: String?
    
    enum CodingKeys: String, CodingKey {
        case mood, energy, timestamp, notes
    }
}

struct MoodUpdate: Codable {
    let mood: String?
    let energy: String?
    let timestamp: Date?
    let notes: String?
    
    enum CodingKeys: String, CodingKey {
        case mood, energy, timestamp, notes
    }
}

struct MoodListResponse: Codable {
    let items: [Mood]
    let total: Int
    let limit: Int
    let offset: Int
}

// ============================================================================
// MARK: - Analytics Models
// ============================================================================

struct AnalyticsSummary: Codable {
    struct CountByDay: Codable {
        let date: String
        let count: Int
    }
    
    struct HoursByDay: Codable {
        let date: String
        let hours: Double
    }
    
    struct Totals: Codable {
        let feedings: Int
        let diapers: Int
        let avgSleepHoursPerDay: Double
        
        enum CodingKeys: String, CodingKey {
            case feedings, diapers
            case avgSleepHoursPerDay = "avgSleepHoursPerDay"
        }
    }
    
    let rangeDays: Int
    let feedingCountByDay: [CountByDay]
    let diaperCountByDay: [CountByDay]
    let sleepHoursByDay: [HoursByDay]
    let totals: Totals
    
    enum CodingKeys: String, CodingKey {
        case rangeDays = "rangeDays"
        case feedingCountByDay = "feedingCountByDay"
        case diaperCountByDay = "diaperCountByDay"
        case sleepHoursByDay = "sleepHoursByDay"
        case totals
    }
}

// ============================================================================
// MARK: - Error Handling
// ============================================================================

enum APIError: LocalizedError {
    case invalidURL
    case decodingError(Error)
    case networkError(Error)
    case unauthorized
    case notFound
    case validationError(String)
    case serverError(String)
    
    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Invalid URL"
        case .decodingError(let error):
            return "Decoding error: \(error.localizedDescription)"
        case .networkError(let error):
            return "Network error: \(error.localizedDescription)"
        case .unauthorized:
            return "Unauthorized - Invalid or missing authentication"
        case .notFound:
            return "Resource not found"
        case .validationError(let message):
            return "Validation error: \(message)"
        case .serverError(let message):
            return "Server error: \(message)"
        }
    }
}

// ============================================================================
// MARK: - API Client
// ============================================================================

class NurtureAPI {
    static let shared = NurtureAPI()
    
    private let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return decoder
    }()
    
    private let encoder: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        return encoder
    }()
    
    private var authToken: String?
    
    // MARK: - Setup
    
    func setAuthToken(_ token: String) {
        self.authToken = token
    }
    
    private func makeRequest(
        method: String,
        endpoint: String,
        body: Encodable? = nil
    ) -> URLRequest {
        let url = URL(string: "\(NurtureConfig.baseURL)\(endpoint)")!
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.timeoutInterval = NurtureConfig.timeout
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        if let token = authToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        
        if let body = body {
            request.httpBody = try? encoder.encode(body)
        }
        
        return request
    }
    
    private func perform<T: Decodable>(request: URLRequest) async throws -> T {
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.networkError(NSError(domain: "Invalid response", code: -1))
        }
        
        switch httpResponse.statusCode {
        case 200...299:
            return try decoder.decode(T.self, from: data)
        case 401:
            throw APIError.unauthorized
        case 404:
            throw APIError.notFound
        case 422:
            if let errorResponse = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let detail = errorResponse["detail"] as? String {
                throw APIError.validationError(detail)
            }
            throw APIError.validationError("Validation error")
        case 500...:
            if let errorResponse = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let detail = errorResponse["detail"] as? String {
                throw APIError.serverError(detail)
            }
            throw APIError.serverError("Server error")
        default:
            throw APIError.networkError(NSError(domain: "HTTP \(httpResponse.statusCode)", code: httpResponse.statusCode))
        }
    }
    
    // MARK: - Auth
    
    /// POST /auth/session
    func createSession() async throws -> SessionResponse {
        let request = makeRequest(method: "POST", endpoint: "/auth/session")
        return try await perform(request: request)
    }
    
    // MARK: - Babies
    
    /// GET /babies
    func listBabies(limit: Int = 20, offset: Int = 0) async throws -> BabyListResponse {
        let endpoint = "/babies?limit=\(limit)&offset=\(offset)"
        let request = makeRequest(method: "GET", endpoint: endpoint)
        return try await perform(request: request)
    }
    
    /// POST /babies
    func createBaby(name: String, birthDate: Date, photoUrl: String? = nil) async throws -> Baby {
        let baby = BabyCreate(name: name, birthDate: birthDate, photoUrl: photoUrl)
        let request = makeRequest(method: "POST", endpoint: "/babies", body: baby)
        return try await perform(request: request)
    }
    
    /// GET /babies/{baby_id}
    func getBaby(id: UUID) async throws -> Baby {
        let request = makeRequest(method: "GET", endpoint: "/babies/\(id.uuidString)")
        return try await perform(request: request)
    }
    
    /// PUT /babies/{baby_id}
    func updateBaby(
        id: UUID,
        name: String? = nil,
        birthDate: Date? = nil,
        photoUrl: String? = nil
    ) async throws -> Baby {
        let update = BabyUpdate(name: name, birthDate: birthDate, photoUrl: photoUrl)
        let request = makeRequest(method: "PUT", endpoint: "/babies/\(id.uuidString)", body: update)
        return try await perform(request: request)
    }
    
    /// DELETE /babies/{baby_id}
    func deleteBaby(id: UUID) async throws {
        let request = makeRequest(method: "DELETE", endpoint: "/babies/\(id.uuidString)")
        let (_, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw APIError.serverError("Failed to delete baby")
        }
    }
    
    // MARK: - Feeding
    
    /// GET /babies/{baby_id}/feedings
    func listFeedings(
        babyId: UUID,
        limit: Int = 20,
        offset: Int = 0,
        fromTime: Date? = nil,
        toTime: Date? = nil
    ) async throws -> FeedingListResponse {
        var endpoint = "/babies/\(babyId.uuidString)/feedings?limit=\(limit)&offset=\(offset)"
        if let fromTime = fromTime {
            endpoint += "&from_time=\(ISO8601DateFormatter().string(from: fromTime))"
        }
        if let toTime = toTime {
            endpoint += "&to_time=\(ISO8601DateFormatter().string(from: toTime))"
        }
        let request = makeRequest(method: "GET", endpoint: endpoint)
        return try await perform(request: request)
    }
    
    /// POST /babies/{baby_id}/feedings
    func createFeeding(
        babyId: UUID,
        feedingType: String,
        amountMl: Int? = nil,
        durationMin: Int? = nil,
        timestamp: Date = Date(),
        notes: String? = nil
    ) async throws -> Feeding {
        let feeding = FeedingCreate(
            feedingType: feedingType,
            amountMl: amountMl,
            durationMin: durationMin,
            timestamp: timestamp,
            notes: notes
        )
        let request = makeRequest(method: "POST", endpoint: "/babies/\(babyId.uuidString)/feedings", body: feeding)
        return try await perform(request: request)
    }
    
    /// PUT /feedings/{feeding_id}
    func updateFeeding(
        id: UUID,
        feedingType: String? = nil,
        amountMl: Int? = nil,
        durationMin: Int? = nil,
        timestamp: Date? = nil,
        notes: String? = nil
    ) async throws -> Feeding {
        let update = FeedingUpdate(
            feedingType: feedingType,
            amountMl: amountMl,
            durationMin: durationMin,
            timestamp: timestamp,
            notes: notes
        )
        let request = makeRequest(method: "PUT", endpoint: "/feedings/\(id.uuidString)", body: update)
        return try await perform(request: request)
    }
    
    /// DELETE /feedings/{feeding_id}
    func deleteFeeding(id: UUID) async throws {
        let request = makeRequest(method: "DELETE", endpoint: "/feedings/\(id.uuidString)")
        let (_, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw APIError.serverError("Failed to delete feeding")
        }
    }
    
    // MARK: - Diaper
    
    /// GET /babies/{baby_id}/diapers
    func listDiapers(
        babyId: UUID,
        limit: Int = 20,
        offset: Int = 0,
        fromTime: Date? = nil,
        toTime: Date? = nil
    ) async throws -> DiaperListResponse {
        var endpoint = "/babies/\(babyId.uuidString)/diapers?limit=\(limit)&offset=\(offset)"
        if let fromTime = fromTime {
            endpoint += "&from_time=\(ISO8601DateFormatter().string(from: fromTime))"
        }
        if let toTime = toTime {
            endpoint += "&to_time=\(ISO8601DateFormatter().string(from: toTime))"
        }
        let request = makeRequest(method: "GET", endpoint: endpoint)
        return try await perform(request: request)
    }
    
    /// POST /babies/{baby_id}/diapers
    func createDiaper(
        babyId: UUID,
        diaperType: String,
        timestamp: Date = Date(),
        notes: String? = nil
    ) async throws -> Diaper {
        let diaper = DiaperCreate(diaperType: diaperType, timestamp: timestamp, notes: notes)
        let request = makeRequest(method: "POST", endpoint: "/babies/\(babyId.uuidString)/diapers", body: diaper)
        return try await perform(request: request)
    }
    
    /// PUT /diapers/{diaper_id}
    func updateDiaper(
        id: UUID,
        diaperType: String? = nil,
        timestamp: Date? = nil,
        notes: String? = nil
    ) async throws -> Diaper {
        let update = DiaperUpdate(diaperType: diaperType, timestamp: timestamp, notes: notes)
        let request = makeRequest(method: "PUT", endpoint: "/diapers/\(id.uuidString)", body: update)
        return try await perform(request: request)
    }
    
    /// DELETE /diapers/{diaper_id}
    func deleteDiaper(id: UUID) async throws {
        let request = makeRequest(method: "DELETE", endpoint: "/diapers/\(id.uuidString)")
        let (_, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw APIError.serverError("Failed to delete diaper")
        }
    }
    
    // MARK: - Sleep
    
    /// GET /babies/{baby_id}/sleep
    func listSleep(
        babyId: UUID,
        limit: Int = 20,
        offset: Int = 0,
        fromTime: Date? = nil,
        toTime: Date? = nil
    ) async throws -> SleepListResponse {
        var endpoint = "/babies/\(babyId.uuidString)/sleep?limit=\(limit)&offset=\(offset)"
        if let fromTime = fromTime {
            endpoint += "&from_time=\(ISO8601DateFormatter().string(from: fromTime))"
        }
        if let toTime = toTime {
            endpoint += "&to_time=\(ISO8601DateFormatter().string(from: toTime))"
        }
        let request = makeRequest(method: "GET", endpoint: endpoint)
        return try await perform(request: request)
    }
    
    /// POST /babies/{baby_id}/sleep
    func createSleep(
        babyId: UUID,
        startTime: Date,
        endTime: Date? = nil,
        durationMin: Int? = nil,
        quality: String? = nil,
        notes: String? = nil
    ) async throws -> Sleep {
        let sleep = SleepCreate(
            startTime: startTime,
            endTime: endTime,
            durationMin: durationMin,
            quality: quality,
            notes: notes
        )
        let request = makeRequest(method: "POST", endpoint: "/babies/\(babyId.uuidString)/sleep", body: sleep)
        return try await perform(request: request)
    }
    
    /// PUT /sleep/{sleep_id}
    func updateSleep(
        id: UUID,
        startTime: Date? = nil,
        endTime: Date? = nil,
        durationMin: Int? = nil,
        quality: String? = nil,
        notes: String? = nil
    ) async throws -> Sleep {
        let update = SleepUpdate(
            startTime: startTime,
            endTime: endTime,
            durationMin: durationMin,
            quality: quality,
            notes: notes
        )
        let request = makeRequest(method: "PUT", endpoint: "/sleep/\(id.uuidString)", body: update)
        return try await perform(request: request)
    }
    
    /// DELETE /sleep/{sleep_id}
    func deleteSleep(id: UUID) async throws {
        let request = makeRequest(method: "DELETE", endpoint: "/sleep/\(id.uuidString)")
        let (_, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw APIError.serverError("Failed to delete sleep")
        }
    }
    
    // MARK: - Mood
    
    /// GET /babies/{baby_id}/moods
    func listMoods(
        babyId: UUID,
        limit: Int = 20,
        offset: Int = 0,
        fromTime: Date? = nil,
        toTime: Date? = nil
    ) async throws -> MoodListResponse {
        var endpoint = "/babies/\(babyId.uuidString)/moods?limit=\(limit)&offset=\(offset)"
        if let fromTime = fromTime {
            endpoint += "&from_time=\(ISO8601DateFormatter().string(from: fromTime))"
        }
        if let toTime = toTime {
            endpoint += "&to_time=\(ISO8601DateFormatter().string(from: toTime))"
        }
        let request = makeRequest(method: "GET", endpoint: endpoint)
        return try await perform(request: request)
    }
    
    /// POST /babies/{baby_id}/moods
    func createMood(
        babyId: UUID,
        mood: String,
        energy: String,
        timestamp: Date = Date(),
        notes: String? = nil
    ) async throws -> Mood {
        let moodEntry = MoodCreate(mood: mood, energy: energy, timestamp: timestamp, notes: notes)
        let request = makeRequest(method: "POST", endpoint: "/babies/\(babyId.uuidString)/moods", body: moodEntry)
        return try await perform(request: request)
    }
    
    /// PUT /moods/{mood_id}
    func updateMood(
        id: UUID,
        mood: String? = nil,
        energy: String? = nil,
        timestamp: Date? = nil,
        notes: String? = nil
    ) async throws -> Mood {
        let update = MoodUpdate(mood: mood, energy: energy, timestamp: timestamp, notes: notes)
        let request = makeRequest(method: "PUT", endpoint: "/moods/\(id.uuidString)", body: update)
        return try await perform(request: request)
    }
    
    /// DELETE /moods/{mood_id}
    func deleteMood(id: UUID) async throws {
        let request = makeRequest(method: "DELETE", endpoint: "/moods/\(id.uuidString)")
        let (_, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw APIError.serverError("Failed to delete mood")
        }
    }
    
    // MARK: - Analytics
    
    /// GET /babies/{baby_id}/analytics/summary?range_days={days}
    func getAnalyticsSummary(babyId: UUID, rangeDays: Int = 7) async throws -> AnalyticsSummary {
        let endpoint = "/babies/\(babyId.uuidString)/analytics/summary?range_days=\(rangeDays)"
        let request = makeRequest(method: "GET", endpoint: endpoint)
        return try await perform(request: request)
    }
}

// ============================================================================
// MARK: - Usage Examples
// ============================================================================

/*
 
 // MARK: - Setup in AppDelegate or App.swift
 
 @main
 struct NurtureApp: App {
     var body: some Scene {
         WindowGroup {
             ContentView()
                 .onAppear {
                     // After Firebase authentication
                     let apiClient = NurtureAPI.shared
                     apiClient.setAuthToken(firebaseIdToken)
                 }
         }
     }
 }
 
 // MARK: - Example: Create Session
 
 @MainActor
 class AuthViewModel: ObservableObject {
     @Published var userId: String?
     private let api = NurtureAPI.shared
     
     func createSession() {
         Task {
             do {
                 let session = try await api.createSession()
                 self.userId = session.userId
             } catch {
                 print("Error: \(error.localizedDescription)")
             }
         }
     }
 }
 
 // MARK: - Example: List Babies
 
 @MainActor
 class BabiesViewModel: ObservableObject {
     @Published var babies: [Baby] = []
     @Published var isLoading = false
     @Published var errorMessage: String?
     
     private let api = NurtureAPI.shared
     
     func loadBabies() {
         isLoading = true
         Task {
             do {
                 let response = try await api.listBabies(limit: 20, offset: 0)
                 self.babies = response.items
                 self.isLoading = false
             } catch {
                 self.errorMessage = error.localizedDescription
                 self.isLoading = false
             }
         }
     }
     
     func createBaby(name: String, birthDate: Date) {
         Task {
             do {
                 let baby = try await api.createBaby(name: name, birthDate: birthDate)
                 self.babies.append(baby)
             } catch {
                 self.errorMessage = error.localizedDescription
             }
         }
     }
 }
 
 // MARK: - Example: Create Feeding
 
 @MainActor
 class FeedingViewModel: ObservableObject {
     @Published var feedings: [Feeding] = []
     
     private let api = NurtureAPI.shared
     let babyId: UUID
     
     init(babyId: UUID) {
         self.babyId = babyId
     }
     
     func loadFeedings() {
         Task {
             do {
                 let response = try await api.listFeedings(babyId: babyId)
                 self.feedings = response.items
             } catch {
                 print("Error: \(error.localizedDescription)")
             }
         }
     }
     
     func addFeeding(type: String, amount: Int, duration: Int, notes: String) {
         Task {
             do {
                 let feeding = try await api.createFeeding(
                     babyId: babyId,
                     feedingType: type,
                     amountMl: amount,
                     durationMin: duration,
                     timestamp: Date(),
                     notes: notes
                 )
                 self.feedings.insert(feeding, at: 0)
             } catch {
                 print("Error: \(error.localizedDescription)")
             }
         }
     }
 }
 
 // MARK: - Example: Get Analytics for Chart
 
 @MainActor
 class AnalyticsViewModel: ObservableObject {
     @Published var analytics: AnalyticsSummary?
     @Published var isLoading = false
     
     private let api = NurtureAPI.shared
     let babyId: UUID
     
     init(babyId: UUID) {
         self.babyId = babyId
     }
     
     func loadAnalytics(days: Int = 7) {
         isLoading = true
         Task {
             do {
                 self.analytics = try await api.getAnalyticsSummary(babyId: babyId, rangeDays: days)
                 self.isLoading = false
             } catch {
                 print("Error: \(error.localizedDescription)")
                 self.isLoading = false
             }
         }
     }
 }
 
 // MARK: - Example: SwiftUI View
 
 struct BabyDetailView: View {
     @StateObject var feedingVM: FeedingViewModel
     @StateObject var analyticsVM: AnalyticsViewModel
     
     var body: some View {
         VStack {
             // Recent feedings list
             List {
                 ForEach(feedingVM.feedings) { feeding in
                     VStack(alignment: .leading) {
                         Text(feeding.feedingType).font(.headline)
                         if let amount = feeding.amountMl {
                             Text("\(amount) ml").font(.caption)
                         }
                     }
                 }
             }
             
             // Analytics chart
             if let analytics = analyticsVM.analytics {
                 VStack {
                     Text("7-Day Summary")
                     Text("Total Feedings: \(analytics.totals.feedings)")
                     Text("Avg Sleep: \(analytics.totals.avgSleepHoursPerDay) hrs")
                 }
             }
         }
         .onAppear {
             feedingVM.loadFeedings()
             analyticsVM.loadAnalytics()
         }
     }
 }
 
*/
