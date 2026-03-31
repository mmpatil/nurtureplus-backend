import SwiftUI

// MARK: - iOS Xcode Integration Examples

// ============================================================================
// SECTION 1: Setup (Call Once in App)
// ============================================================================

@main
struct NurtureApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject var authManager = AuthManager.shared
    
    var body: some Scene {
        WindowGroup {
            if authManager.isAuthenticated {
                MainTabView()
            } else {
                LoginView()
            }
        }
    }
}

class AppDelegate: UIResponder, UIApplicationDelegate {
    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
    ) -> Bool {
        // Initialize Firebase, etc.
        FirebaseApp.configure()
        return true
    }
}

// ============================================================================
// SECTION 2: Auth Manager (Manages API Token)
// ============================================================================

@MainActor
class AuthManager: NSObject, ObservableObject {
    static let shared = AuthManager()
    
    @Published var isAuthenticated = false
    @Published var currentUser: SessionResponse?
    @Published var firebaseToken: String?
    
    override init() {
        super.init()
    }
    
    func loginWithFirebase(idToken: String) async {
        NurtureAPI.shared.setAuthToken(idToken)
        self.firebaseToken = idToken
        
        do {
            let session = try await NurtureAPI.shared.createSession()
            self.currentUser = session
            self.isAuthenticated = true
        } catch {
            print("Login failed: \(error.localizedDescription)")
        }
    }
    
    func logout() {
        self.isAuthenticated = false
        self.currentUser = nil
        self.firebaseToken = nil
    }
}

// ============================================================================
// SECTION 3: Babies Manager
// ============================================================================

@MainActor
class BabiesManager: ObservableObject {
    @Published var babies: [Baby] = []
    @Published var isLoading = false
    @Published var errorMessage: String?
    
    private let api = NurtureAPI.shared
    
    func loadBabies() {
        isLoading = true
        errorMessage = nil
        
        Task {
            do {
                let response = try await api.listBabies(limit: 50, offset: 0)
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
                self.babies.insert(baby, at: 0)
                self.errorMessage = nil
            } catch {
                self.errorMessage = error.localizedDescription
            }
        }
    }
    
    func updateBaby(id: UUID, name: String, birthDate: Date) {
        Task {
            do {
                let baby = try await api.updateBaby(id: id, name: name, birthDate: birthDate)
                if let index = babies.firstIndex(where: { $0.id == id }) {
                    babies[index] = baby
                }
                self.errorMessage = nil
            } catch {
                self.errorMessage = error.localizedDescription
            }
        }
    }
    
    func deleteBaby(id: UUID) {
        Task {
            do {
                try await api.deleteBaby(id: id)
                babies.removeAll { $0.id == id }
                self.errorMessage = nil
            } catch {
                self.errorMessage = error.localizedDescription
            }
        }
    }
}

// ============================================================================
// SECTION 4: Feeding Manager
// ============================================================================

@MainActor
class FeedingManager: ObservableObject {
    @Published var feedings: [Feeding] = []
    @Published var isLoading = false
    @Published var errorMessage: String?
    
    private let api = NurtureAPI.shared
    let babyId: UUID
    
    init(babyId: UUID) {
        self.babyId = babyId
    }
    
    func loadFeedings(days: Int = 7) {
        isLoading = true
        errorMessage = nil
        
        let fromDate = Calendar.current.date(byAdding: .day, value: -days, to: Date())!
        
        Task {
            do {
                let response = try await api.listFeedings(
                    babyId: babyId,
                    limit: 50,
                    offset: 0,
                    fromTime: fromDate,
                    toTime: Date()
                )
                self.feedings = response.items.sorted { $0.timestamp > $1.timestamp }
                self.isLoading = false
            } catch {
                self.errorMessage = error.localizedDescription
                self.isLoading = false
            }
        }
    }
    
    func addFeeding(type: String, amount: Int?, duration: Int?, notes: String? = nil) {
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
                self.errorMessage = nil
            } catch {
                self.errorMessage = error.localizedDescription
            }
        }
    }
    
    func updateFeeding(id: UUID, type: String?, amount: Int?, duration: Int?, notes: String?) {
        Task {
            do {
                let feeding = try await api.updateFeeding(
                    id: id,
                    feedingType: type,
                    amountMl: amount,
                    durationMin: duration,
                    notes: notes
                )
                if let index = feedings.firstIndex(where: { $0.id == id }) {
                    feedings[index] = feeding
                }
            } catch {
                self.errorMessage = error.localizedDescription
            }
        }
    }
    
    func deleteFeeding(id: UUID) {
        Task {
            do {
                try await api.deleteFeeding(id: id)
                feedings.removeAll { $0.id == id }
            } catch {
                self.errorMessage = error.localizedDescription
            }
        }
    }
}

// ============================================================================
// SECTION 5: Diaper Manager
// ============================================================================

@MainActor
class DiaperManager: ObservableObject {
    @Published var diapers: [Diaper] = []
    @Published var isLoading = false
    @Published var errorMessage: String?
    
    private let api = NurtureAPI.shared
    let babyId: UUID
    
    init(babyId: UUID) {
        self.babyId = babyId
    }
    
    func loadDiapers(days: Int = 7) {
        isLoading = true
        let fromDate = Calendar.current.date(byAdding: .day, value: -days, to: Date())!
        
        Task {
            do {
                let response = try await api.listDiapers(
                    babyId: babyId,
                    limit: 50,
                    offset: 0,
                    fromTime: fromDate,
                    toTime: Date()
                )
                self.diapers = response.items.sorted { $0.timestamp > $1.timestamp }
                self.isLoading = false
            } catch {
                self.errorMessage = error.localizedDescription
                self.isLoading = false
            }
        }
    }
    
    func addDiaper(type: String, notes: String? = nil) {
        Task {
            do {
                let diaper = try await api.createDiaper(
                    babyId: babyId,
                    diaperType: type,
                    timestamp: Date(),
                    notes: notes
                )
                self.diapers.insert(diaper, at: 0)
            } catch {
                self.errorMessage = error.localizedDescription
            }
        }
    }
    
    func deleteDiaper(id: UUID) {
        Task {
            do {
                try await api.deleteDiaper(id: id)
                diapers.removeAll { $0.id == id }
            } catch {
                self.errorMessage = error.localizedDescription
            }
        }
    }
}

// ============================================================================
// SECTION 6: Sleep Manager
// ============================================================================

@MainActor
class SleepManager: ObservableObject {
    @Published var sleepSessions: [Sleep] = []
    @Published var isLoading = false
    @Published var errorMessage: String?
    
    private let api = NurtureAPI.shared
    let babyId: UUID
    
    init(babyId: UUID) {
        self.babyId = babyId
    }
    
    func loadSleep(days: Int = 7) {
        isLoading = true
        let fromDate = Calendar.current.date(byAdding: .day, value: -days, to: Date())!
        
        Task {
            do {
                let response = try await api.listSleep(
                    babyId: babyId,
                    limit: 50,
                    offset: 0,
                    fromTime: fromDate,
                    toTime: Date()
                )
                self.sleepSessions = response.items.sorted { $0.startTime > $1.startTime }
                self.isLoading = false
            } catch {
                self.errorMessage = error.localizedDescription
                self.isLoading = false
            }
        }
    }
    
    func logSleep(startTime: Date, endTime: Date? = nil, quality: String? = nil, notes: String? = nil) {
        Task {
            do {
                let sleep = try await api.createSleep(
                    babyId: babyId,
                    startTime: startTime,
                    endTime: endTime,
                    quality: quality,
                    notes: notes
                )
                self.sleepSessions.insert(sleep, at: 0)
            } catch {
                self.errorMessage = error.localizedDescription
            }
        }
    }
    
    func updateSleep(id: UUID, endTime: Date, quality: String) {
        Task {
            do {
                let sleep = try await api.updateSleep(
                    id: id,
                    endTime: endTime,
                    quality: quality
                )
                if let index = sleepSessions.firstIndex(where: { $0.id == id }) {
                    sleepSessions[index] = sleep
                }
            } catch {
                self.errorMessage = error.localizedDescription
            }
        }
    }
}

// ============================================================================
// SECTION 7: Mood Manager
// ============================================================================

@MainActor
class MoodManager: ObservableObject {
    @Published var moods: [Mood] = []
    @Published var isLoading = false
    @Published var errorMessage: String?
    
    private let api = NurtureAPI.shared
    let babyId: UUID
    
    init(babyId: UUID) {
        self.babyId = babyId
    }
    
    func loadMoods(days: Int = 7) {
        isLoading = true
        let fromDate = Calendar.current.date(byAdding: .day, value: -days, to: Date())!
        
        Task {
            do {
                let response = try await api.listMoods(
                    babyId: babyId,
                    limit: 50,
                    offset: 0,
                    fromTime: fromDate,
                    toTime: Date()
                )
                self.moods = response.items.sorted { $0.timestamp > $1.timestamp }
                self.isLoading = false
            } catch {
                self.errorMessage = error.localizedDescription
                self.isLoading = false
            }
        }
    }
    
    func logMood(mood: String, energy: String, notes: String? = nil) {
        Task {
            do {
                let moodEntry = try await api.createMood(
                    babyId: babyId,
                    mood: mood,
                    energy: energy,
                    timestamp: Date(),
                    notes: notes
                )
                self.moods.insert(moodEntry, at: 0)
            } catch {
                self.errorMessage = error.localizedDescription
            }
        }
    }
}

// ============================================================================
// SECTION 8: Analytics Manager
// ============================================================================

@MainActor
class AnalyticsManager: ObservableObject {
    @Published var analytics: AnalyticsSummary?
    @Published var isLoading = false
    @Published var errorMessage: String?
    
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
                self.errorMessage = error.localizedDescription
                self.isLoading = false
            }
        }
    }
}

// ============================================================================
// SECTION 9: UI Components - Babies List
// ============================================================================

struct BabiesListView: View {
    @StateObject var babyManager = BabiesManager()
    @State var showingAddBaby = false
    
    var body: some View {
        NavigationStack {
            VStack {
                if babyManager.isLoading {
                    ProgressView()
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else {
                    List {
                        ForEach(babyManager.babies) { baby in
                            NavigationLink(destination: BabyDetailView(baby: baby)) {
                                VStack(alignment: .leading) {
                                    Text(baby.name).font(.headline)
                                    Text(baby.birthDate.formatted(date: .abbreviated, time: .omitted))
                                        .font(.caption)
                                        .foregroundColor(.gray)
                                }
                            }
                        }
                        .onDelete { indexSet in
                            indexSet.forEach { index in
                                babyManager.deleteBaby(id: babyManager.babies[index].id)
                            }
                        }
                    }
                }
            }
            .navigationTitle("My Babies")
            .toolbar {
                Button("Add") {
                    showingAddBaby = true
                }
            }
            .sheet(isPresented: $showingAddBaby) {
                AddBabyView(babyManager: babyManager)
            }
            .alert("Error", isPresented: .constant(babyManager.errorMessage != nil), presenting: babyManager.errorMessage) { _ in
                Button("OK") { babyManager.errorMessage = nil }
            } message: { message in
                Text(message)
            }
        }
        .onAppear {
            babyManager.loadBabies()
        }
    }
}

// ============================================================================
// SECTION 10: UI Components - Baby Detail
// ============================================================================

struct BabyDetailView: View {
    let baby: Baby
    @StateObject var feedingManager: FeedingManager
    @StateObject var diaperManager: DiaperManager
    @StateObject var sleepManager: SleepManager
    @StateObject var analyticsManager: AnalyticsManager
    @State var selectedTab = 0
    
    init(baby: Baby) {
        self.baby = baby
        _feedingManager = StateObject(wrappedValue: FeedingManager(babyId: baby.id))
        _diaperManager = StateObject(wrappedValue: DiaperManager(babyId: baby.id))
        _sleepManager = StateObject(wrappedValue: SleepManager(babyId: baby.id))
        _analyticsManager = StateObject(wrappedValue: AnalyticsManager(babyId: baby.id))
    }
    
    var body: some View {
        VStack {
            // Header
            VStack {
                Text(baby.name).font(.title)
                Text("Born: \(baby.birthDate.formatted(date: .abbreviated, time: .omitted))")
                    .font(.caption)
            }
            .padding()
            
            // Tabs
            Picker("", selection: $selectedTab) {
                Text("Feeding").tag(0)
                Text("Diapers").tag(1)
                Text("Sleep").tag(2)
                Text("Mood").tag(3)
                Text("Analytics").tag(4)
            }
            .pickerStyle(.segmented)
            .padding()
            
            // Tab Content
            TabView(selection: $selectedTab) {
                FeedingTabView(manager: feedingManager)
                    .tag(0)
                
                DiaperTabView(manager: diaperManager)
                    .tag(1)
                
                SleepTabView(manager: sleepManager)
                    .tag(2)
                
                MoodTabView(babyId: baby.id)
                    .tag(3)
                
                AnalyticsTabView(manager: analyticsManager)
                    .tag(4)
            }
            .tabViewStyle(.page(indexDisplayMode: .never))
            
            Spacer()
        }
        .navigationTitle("Tracking")
        .onAppear {
            feedingManager.loadFeedings()
            diaperManager.loadDiapers()
            sleepManager.loadSleep()
            analyticsManager.loadAnalytics()
        }
    }
}

// ============================================================================
// SECTION 11: Tab Views - Feeding
// ============================================================================

struct FeedingTabView: View {
    @ObservedObject var manager: FeedingManager
    @State var showingAddFeeding = false
    
    var body: some View {
        VStack {
            List {
                ForEach(manager.feedings) { feeding in
                    VStack(alignment: .leading) {
                        Text(feeding.feedingType)
                            .font(.headline)
                        HStack {
                            if let amount = feeding.amountMl {
                                Label("\(amount) ml", systemImage: "drop")
                            }
                            if let duration = feeding.durationMin {
                                Label("\(duration) min", systemImage: "clock")
                            }
                        }
                        .font(.caption)
                        
                        Text(feeding.timestamp.formatted(date: .abbreviated, time:.shortened))
                            .font(.caption2)
                            .foregroundColor(.gray)
                    }
                }
                .onDelete { indexSet in
                    indexSet.forEach { index in
                        manager.deleteFeeding(id: manager.feedings[index].id)
                    }
                }
            }
        }
        .toolbar {
            Button("Add Feeding") {
                showingAddFeeding = true
            }
        }
        .sheet(isPresented: $showingAddFeeding) {
            AddFeedingView(manager: manager)
        }
    }
}

struct AddFeedingView: View {
    @ObservedObject var manager: FeedingManager
    @Environment(\.dismiss) var dismiss
    
    @State var feedingType = "bottle"
    @State var amount = ""
    @State var duration = ""
    @State var notes = ""
    
    var body: some View {
        NavigationStack {
            Form {
                Picker("Type", selection: $feedingType) {
                    Text("Bottle").tag("bottle")
                    Text("Breast Left").tag("breast_left")
                    Text("Breast Right").tag("breast_right")
                    Text("Both").tag("both")
                }
                
                TextField("Amount (ml)", text: $amount)
                    .keyboardType(.numberPad)
                
                TextField("Duration (min)", text: $duration)
                    .keyboardType(.numberPad)
                
                TextField("Notes", text: $notes)
            }
            .navigationTitle("Log Feeding")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        manager.addFeeding(
                            type: feedingType,
                            amount: Int(amount),
                            duration: Int(duration),
                            notes: notes.isEmpty ? nil : notes
                        )
                        dismiss()
                    }
                }
            }
        }
    }
}

// ============================================================================
// SECTION 12: Tab Views - Diaper
// ============================================================================

struct DiaperTabView: View {
    @ObservedObject var manager: DiaperManager
    @State var showingAddDiaper = false
    
    var body: some View {
        VStack {
            List {
                ForEach(manager.diapers) { diaper in
                    VStack(alignment: .leading) {
                        HStack {
                            Image(systemName: getDiaperIcon(diaper.diaperType))
                            Text(diaper.diaperType)
                                .font(.headline)
                        }
                        
                        Text(diaper.timestamp.formatted(date: .abbreviated, time: .shortened))
                            .font(.caption2)
                            .foregroundColor(.gray)
                    }
                }
                .onDelete { indexSet in
                    indexSet.forEach { index in
                        manager.deleteDiaper(id: manager.diapers[index].id)
                    }
                }
            }
        }
        .toolbar {
            Button("Add Diaper") {
                showingAddDiaper = true
            }
        }
        .sheet(isPresented: $showingAddDiaper) {
            AddDiaperView(manager: manager)
        }
    }
    
    func getDiaperIcon(_ type: String) -> String {
        switch type {
        case "wet": return "droplet"
        case "dirty": return "exclamationmark"
        case "both": return "exclamationmark.circle"
        default: return "circle"
        }
    }
}

struct AddDiaperView: View {
    @ObservedObject var manager: DiaperManager
    @Environment(\.dismiss) var dismiss
    
    @State var diaperType = "wet"
    @State var notes = ""
    
    var body: some View {
        NavigationStack {
            Form {
                Picker("Type", selection: $diaperType) {
                    Text("Wet").tag("wet")
                    Text("Dirty").tag("dirty")
                    Text("Both").tag("both")
                    Text("Dry").tag("dry")
                }
                
                TextField("Notes", text: $notes)
            }
            .navigationTitle("Log Diaper")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        manager.addDiaper(
                            type: diaperType,
                            notes: notes.isEmpty ? nil : notes
                        )
                        dismiss()
                    }
                }
            }
        }
    }
}

// ============================================================================
// SECTION 13: Tab Views - Sleep
// ============================================================================

struct SleepTabView: View {
    @ObservedObject var manager: SleepManager
    @State var showingAddSleep = false
    
    var body: some View {
        VStack {
            List {
                ForEach(manager.sleepSessions) { sleep in
                    VStack(alignment: .leading) {
                        HStack {
                            Image(systemName: "moon")
                            Text("\(sleep.durationMin ?? 0) min")
                                .font(.headline)
                        }
                        
                        if let quality = sleep.quality {
                            Text("Quality: \(quality)")
                                .font(.caption)
                        }
                        
                        Text(sleep.startTime.formatted(date: .abbreviated, time: .shortened))
                            .font(.caption2)
                            .foregroundColor(.gray)
                    }
                }
            }
        }
        .toolbar {
            Button("Log Sleep") {
                showingAddSleep = true
            }
        }
        .sheet(isPresented: $showingAddSleep) {
            AddSleepView(manager: manager)
        }
    }
}

struct AddSleepView: View {
    @ObservedObject var manager: SleepManager
    @Environment(\.dismiss) var dismiss
    
    @State var startTime = Date()
    @State var endTime = Date().addingTimeInterval(3600)
    @State var quality = "good"
    @State var notes = ""
    
    var body: some View {
        NavigationStack {
            Form {
                DatePicker("Start", selection: $startTime)
                DatePicker("End", selection: $endTime)
                
                Picker("Quality", selection: $quality) {
                    Text("Great").tag("great")
                    Text("Good").tag("good")
                    Text("Fair").tag("fair")
                    Text("Poor").tag("poor")
                }
                
                TextField("Notes", text: $notes)
            }
            .navigationTitle("Log Sleep")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        manager.logSleep(
                            startTime: startTime,
                            endTime: endTime,
                            quality: quality,
                            notes: notes.isEmpty ? nil : notes
                        )
                        dismiss()
                    }
                }
            }
        }
    }
}

// ============================================================================
// SECTION 14: Tab Views - Mood
// ============================================================================

struct MoodTabView: View {
    let babyId: UUID
    @StateObject var manager: MoodManager
    @State var showingAddMood = false
    
    init(babyId: UUID) {
        self.babyId = babyId
        _manager = StateObject(wrappedValue: MoodManager(babyId: babyId))
    }
    
    var body: some View {
        VStack {
            List {
                ForEach(manager.moods) { mood in
                    VStack(alignment: .leading) {
                        HStack {
                            Text(getMoodEmoji(mood.mood))
                            Text(mood.mood)
                                .font(.headline)
                        }
                        
                        HStack {
                            Image(systemName: "bolt")
                            Text(mood.energy)
                                .font(.caption)
                        }
                        
                        Text(mood.timestamp.formatted(date: .abbreviated, time: .shortened))
                            .font(.caption2)
                            .foregroundColor(.gray)
                    }
                }
            }
        }
        .toolbar {
            Button("Log Mood") {
                showingAddMood = true
            }
        }
        .sheet(isPresented: $showingAddMood) {
            AddMoodView(manager: manager)
        }
        .onAppear {
            manager.loadMoods()
        }
    }
    
    func getMoodEmoji(_ mood: String) -> String {
        switch mood {
        case "happy": return "😊"
        case "sad": return "😢"
        case "anxious": return "😰"
        case "ok": return "😐"
        default: return "🤔"
        }
    }
}

struct AddMoodView: View {
    @ObservedObject var manager: MoodManager
    @Environment(\.dismiss) var dismiss
    
    @State var mood = "happy"
    @State var energy = "high"
    @State var notes = ""
    
    var body: some View {
        NavigationStack {
            Form {
                Picker("Mood", selection: $mood) {
                    Text("😊 Happy").tag("happy")
                    Text("😢 Sad").tag("sad")
                    Text("😰 Anxious").tag("anxious")
                    Text("😐 OK").tag("ok")
                }
                
                Picker("Energy", selection: $energy) {
                    Text("High").tag("high")
                    Text("Medium").tag("medium")
                    Text("Low").tag("low")
                }
                
                TextField("Notes", text: $notes)
            }
            .navigationTitle("Log Mood")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        manager.logMood(
                            mood: mood,
                            energy: energy,
                            notes: notes.isEmpty ? nil : notes
                        )
                        dismiss()
                    }
                }
            }
        }
    }
}

// ============================================================================
// SECTION 15: Tab Views - Analytics
// ============================================================================

struct AnalyticsTabView: View {
    @ObservedObject var manager: AnalyticsManager
    @State var selectedDays = 7
    
    var body: some View {
        VStack {
            Picker("Range", selection: $selectedDays) {
                Text("7 Days").tag(7)
                Text("14 Days").tag(14)
                Text("30 Days").tag(30)
            }
            .pickerStyle(.segmented)
            .padding()
            
            if let analytics = manager.analytics {
                ZStack {
                    ScrollView {
                        VStack(spacing: 20) {
                            // Summary Cards
                            HStack {
                                VStack {
                                    Text("\(analytics.totals.feedings)")
                                        .font(.headline)
                                    Text("Feedings")
                                        .font(.caption)
                                }
                                .frame(maxWidth: .infinity)
                                .padding()
                                .background(Color.blue.opacity(0.1))
                                .cornerRadius(8)
                                
                                VStack {
                                    Text("\(analytics.totals.diapers)")
                                        .font(.headline)
                                    Text("Diapers")
                                        .font(.caption)
                                }
                                .frame(maxWidth: .infinity)
                                .padding()
                                .background(Color.green.opacity(0.1))
                                .cornerRadius(8)
                                
                                VStack {
                                    Text(String(format: "%.1f", analytics.totals.avgSleepHoursPerDay))
                                        .font(.headline)
                                    Text("Sleep Hrs")
                                        .font(.caption)
                                }
                                .frame(maxWidth: .infinity)
                                .padding()
                                .background(Color.purple.opacity(0.1))
                                .cornerRadius(8)
                            }
                            
                            // Charts would go here
                            // For CSV export, you can build a BarChart using Charts framework
                            
                            VStack(alignment: .leading) {
                                Text("Daily Summary")
                                    .font(.headline)
                                
                                ForEach(analytics.feedingCountByDay.prefix(7), id: \.date) { item in
                                    HStack {
                                        Text(item.date)
                                            .font(.caption)
                                        
                                        HStack(spacing: 4) {
                                            Text("🍼\(item.count)")
                                            Text("🩷\(analytics.diaperCountByDay.first(where: { $0.date == item.date })?.count ?? 0)")
                                        }
                                        .font(.caption)
                                        
                                        Spacer()
                                    }
                                    Divider()
                                }
                            }
                            .padding()
                            .background(Color.gray.opacity(0.05))
                            .cornerRadius(8)
                        }
                        .padding()
                    }
                }
            } else if manager.isLoading {
                ProgressView()
            }
        }
        .onChange(of: selectedDays) { newValue in
            manager.loadAnalytics(days: newValue)
        }
    }
}

// ============================================================================
// SECTION 16: Supporting Components
// ============================================================================

struct AddBabyView: View {
    @ObservedObject var babyManager: BabiesManager
    @Environment(\.dismiss) var dismiss
    
    @State var name = ""
    @State var birthDate = Date()
    
    var body: some View {
        NavigationStack {
            Form {
                TextField("Baby Name", text: $name)
                DatePicker("Birth Date", selection: $birthDate, displayedComponents: .date)
            }
            .navigationTitle("Add Baby")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        if !name.isEmpty {
                            babyManager.createBaby(name: name, birthDate: birthDate)
                            dismiss()
                        }
                    }
                    .disabled(name.isEmpty)
                }
            }
        }
    }
}

struct MainTabView: View {
    var body: some View {
        TabView {
            BabiesListView()
                .tabItem {
                    Label("Babies", systemImage: "👶")
                }
            
            Text("More Features Coming")
                .tabItem {
                    Label("More", systemImage: "ellipsis")
                }
        }
    }
}

struct LoginView: View {
    var body: some View {
        VStack {
            Text("Nurture+")
                .font(.title)
            
            Button("Sign in with Firebase") {
                // Integrate with Firebase Auth
            }
            .buttonStyle(.borderedProminent)
        }
    }
}

// MARK: - Preview
#Preview {
    BabiesListView()
}
