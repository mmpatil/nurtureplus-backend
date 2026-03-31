# iOS Integration Quick Start

Copy-paste these 3 files into your Xcode project to integrate all 40 Nurture+ APIs.

---

## 📁 Files to Copy

### File 1: `NurtureAPI.swift`
**What:** Complete API client with all models and endpoints
**Where:** Copy to your Xcode project (e.g., `Networking/NurtureAPI.swift`)
**Size:** ~1,400 lines
**Includes:**
- All 40 endpoint methods
- All data models (Baby, Feeding, Diaper, Sleep, Mood, Analytics)
- Async/await networking
- Error handling
- JSON encoding/decoding
- Firebase Auth token support

### File 2: `SwiftUI_Integration_Examples.swift`
**What:** Complete example app with ViewModels, managers, and UI components
**Where:** Copy to your Xcode project (e.g., `Views/SwiftUI_Integration_Examples.swift`)
**Size:** ~900 lines
**Includes:**
- `AuthManager` - manages Firebase login and API token
- `BabiesManager` - handles baby CRUD
- `FeedingManager` - handles feeding logging
- `DiaperManager` - handles diaper logging
- `SleepManager` - handles sleep logging
- `MoodManager` - handles mood logging
- `AnalyticsManager` - handles analytics data
- Complete SwiftUI Views (List, Detail, Tabs, Forms)
- Example implementations for all features

### File 3: `iOS_API_REFERENCE.md`
**What:** API documentation and reference
**Where:** Keep in project repo (e.g., `docs/iOS_API_REFERENCE.md`)
**Size:** ~400 lines
**Includes:**
- All endpoint definitions
- Request/response examples
- Error handling
- Pagination
- Date format reference
- Quick integration steps

---

## 🚀 Integration Steps

### Step 1: Copy Files
```bash
# In your Xcode project folder
cp NurtureAPI.swift YourProject/Networking/
cp SwiftUI_Integration_Examples.swift YourProject/Views/
cp iOS_API_REFERENCE.md YourProject/docs/
```

### Step 2: Update Base URL
Edit `NurtureAPI.swift`:
```swift
struct NurtureConfig {
    static let baseURL = "http://localhost:8000"  // ← Change this
    static let timeout: TimeInterval = 30
}
```

For production:
```swift
static let baseURL = "https://api.nurture-app.com"  // Your production URL
```

### Step 3: Initialize in App
Edit `App.swift`:
```swift
@main
struct YourApp: App {
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
```

### Step 4: After Firebase Login
In your login handler:
```swift
// After Firebase authentication completes
let firebaseToken = try await Auth.auth().currentUser?.getIDToken()
await AuthManager.shared.loginWithFirebase(idToken: firebaseToken!)
```

### Step 5: Use ViewModels
```swift
@StateObject var babyManager = BabiesManager()  // Manages babies
@StateObject var feedingManager = FeedingManager(babyId: selectedBaby.id)  // Manages feedings
```

---

## 📋 All 40 Endpoints at a Glance

### Auth (1 endpoint)
```swift
try await NurtureAPI.shared.createSession()
```

### Babies (7 endpoints)
```swift
try await NurtureAPI.shared.listBabies()
try await NurtureAPI.shared.createBaby(name:, birthDate:, photoUrl:)
try await NurtureAPI.shared.getBaby(id:)
try await NurtureAPI.shared.updateBaby(id:, name:, birthDate:, photoUrl:)
try await NurtureAPI.shared.deleteBaby(id:)
```

### Feeding (6 endpoints)
```swift
try await NurtureAPI.shared.listFeedings(babyId:, limit:, offset:, fromTime:, toTime:)
try await NurtureAPI.shared.createFeeding(babyId:, feedingType:, amountMl:, durationMin:, timestamp:, notes:)
try await NurtureAPI.shared.updateFeeding(id:, feedingType:, amountMl:, durationMin:, timestamp:, notes:)
try await NurtureAPI.shared.deleteFeeding(id:)
// Types: "bottle", "breast_left", "breast_right", "both"
```

### Diaper (6 endpoints)
```swift
try await NurtureAPI.shared.listDiapers(babyId:, limit:, offset:, fromTime:, toTime:)
try await NurtureAPI.shared.createDiaper(babyId:, diaperType:, timestamp:, notes:)
try await NurtureAPI.shared.updateDiaper(id:, diaperType:, timestamp:, notes:)
try await NurtureAPI.shared.deleteDiaper(id:)
// Types: "wet", "dirty", "both", "dry"
```

### Sleep (6 endpoints)
```swift
try await NurtureAPI.shared.listSleep(babyId:, limit:, offset:, fromTime:, toTime:)
try await NurtureAPI.shared.createSleep(babyId:, startTime:, endTime:, durationMin:, quality:, notes:)
try await NurtureAPI.shared.updateSleep(id:, startTime:, endTime:, durationMin:, quality:, notes:)
try await NurtureAPI.shared.deleteSleep(id:)
// Quality: "great", "good", "fair", "poor"
```

### Mood (6 endpoints)
```swift
try await NurtureAPI.shared.listMoods(babyId:, limit:, offset:, fromTime:, toTime:)
try await NurtureAPI.shared.createMood(babyId:, mood:, energy:, timestamp:, notes:)
try await NurtureAPI.shared.updateMood(id:, mood:, energy:, timestamp:, notes:)
try await NurtureAPI.shared.deleteMood(id:)
// Mood: "happy", "sad", "anxious", "ok", etc.
// Energy: "high", "medium", "low"
```

### Analytics (1 endpoint)
```swift
try await NurtureAPI.shared.getAnalyticsSummary(babyId:, rangeDays: 7)  // 7, 14, or 30
```

---

## 🎨 Common UI Patterns

### List with Pagination
```swift
@StateObject var manager = BabiesManager()

var body: some View {
    List(manager.babies) { baby in
        NavigationLink(destination: DetailView(baby: baby)) {
            Text(baby.name)
        }
    }
    .onAppear {
        manager.loadBabies()  // Loads first 50
    }
}
```

### Create with Form
```swift
@State var name = ""
@State var date = Date()

var body: some View {
    Form {
        TextField("Name", text: $name)
        DatePicker("Birth Date", selection: $date, displayedComponents: .date)
    }
    .toolbar {
        Button("Save") {
            manager.createBaby(name: name, birthDate: date)
        }
    }
}
```

### Real-time Updates with Async
```swift
@State var feedings: [Feeding] = []

Task {
    do {
        let response = try await NurtureAPI.shared.listFeedings(babyId: babyId)
        self.feedings = response.items
    } catch {
        print("Error: \(error.localizedDescription)")
    }
}
```

---

## 🧪 Testing the API

### Quick Test in Xcode Playground
```swift
import Foundation

// 1. Set token
NurtureAPI.shared.setAuthToken(firebaseToken)

// 2. Test endpoint
Task {
    do {
        let babies = try await NurtureAPI.shared.listBabies()
        print("Found \(babies.total) babies")
    } catch {
        print("Error: \(error)")
    }
}

// Expected output:
// Found 2 babies
```

### Using curl (from Terminal)
```bash
# List babies
curl -H "Authorization: Bearer YOUR_FIREBASE_TOKEN" \
     http://localhost:8000/babies

# Create feeding
curl -X POST \
     -H "Authorization: Bearer YOUR_FIREBASE_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "feeding_type": "bottle",
       "amount_ml": 120,
       "duration_min": 15,
       "timestamp": "2026-03-12T10:30:00Z"
     }' \
     http://localhost:8000/babies/{baby_id}/feedings
```

---

## 🔒 Security Notes

### Firebase Authentication
The API requires a Firebase ID token on every request (except session creation):

```swift
// In your LoginView after Firebase sign-in
let idToken = try await Auth.auth().currentUser?.getIDToken()
NurtureAPI.shared.setAuthToken(idToken!)
```

### Token Refresh
Firebase tokens expire in 1 hour. Refresh when needed:

```swift
@MainActor
class AuthManager {
    func refreshTokenIfNeeded() async throws {
        if shouldRefreshToken {
            let newToken = try await Auth.auth().currentUser?.getIDToken(forceRefresh: true)
            NurtureAPI.shared.setAuthToken(newToken!)
        }
    }
}
```

### Development Mode
For local testing, the backend supports `DEV_BYPASS_AUTH=true` (set in `.env`):

```swift
// Dev mode only - use X-Dev-Uid header
var request = URLRequest(url: url)
request.setValue("test-user-id", forHTTPHeaderField: "X-Dev-Uid")
```

---

## 📊 Chart Integration

### With Charts Framework (iOS 16+)
```swift
import Charts

struct AnalyticsChart: View {
    let analytics: AnalyticsSummary
    
    var body: some View {
        Chart(analytics.feedingCountByDay, id: \.date) { item in
            BarMark(
                x: .value("Date", item.date),
                y: .value("Feedings", item.count)
            )
        }
    }
}
```

### With SwiftUI ZStack (Any iOS version)
```swift
VStack(alignment: .leading) {
    ForEach(analytics.feedingCountByDay, id: \.date) { item in
        HStack {
            Text(item.date).frame(width: 60)
            
            HStack(spacing: 0) {
                ForEach(0..<item.count, id: \.self) { _ in
                    RoundedRectangle(cornerRadius: 2)
                        .fill(Color.blue)
                        .frame(width: 8, height: 16)
                }
            }
        }
    }
}
```

---

## 🐛 Error Handling

### Try-Catch Pattern
```swift
do {
    let feeding = try await NurtureAPI.shared.createFeeding(...)
    print("Created: \(feeding.id)")
} catch let error as APIError {
    switch error {
    case .unauthorized:
        print("Please log in again")
    case .notFound:
        print("Baby not found")
    case .validationError(let msg):
        print("Invalid data: \(msg)")
    case .serverError(let msg):
        print("Server error: \(msg)")
    default:
        print("Error: \(error.localizedDescription)")
    }
} catch {
    print("Unexpected error: \(error)")
}
```

### Error Display in UI
```swift
@State var errorMessage: String?

var body: some View {
    VStack {
        // Content
    }
    .alert("Error", isPresented: .constant(errorMessage != nil), presenting: errorMessage) { _ in
        Button("OK") { errorMessage = nil }
    } message: { msg in
        Text(msg)
    }
}
```

---

## 📱 Device-Specific Considerations

### iPhone Optimizations
- Use `List` for scrollable content
- Provide swipe-to-delete with `.onDelete()`
- Use `@State` for form state

### iPad Optimization
- Use `NavigationSplitView` for master-detail
- Provide landscape support

### Dark Mode
All colors are dynamically set - looks great in both light and dark modes:

```swift
Color.blue.opacity(0.1)  // Automatically adjusts
```

---

## 🔄 State Management Pattern

### Recommended: MVVM with ObservableObject
```swift
@MainActor
class ViewModel: ObservableObject {
    @Published var items: [Item] = []
    @Published var isLoading = false
    @Published var errorMessage: String?
    
    func load() {
        isLoading = true
        Task {
            do {
                self.items = try await api.listItems()
                self.isLoading = false
            } catch {
                self.errorMessage = error.localizedDescription
                self.isLoading = false
            }
        }
    }
}

// In View:
@StateObject var vm = ViewModel()

var body: some View {
    if vm.isLoading {
        ProgressView()
    } else {
        List(vm.items) { item in
            ItemRow(item: item)
        }
    }
}
```

---

## 📚 Additional Resources

- **API Reference:** See `iOS_API_REFERENCE.md`
- **Models:** See `NurtureAPI.swift` (lines 1-300)
- **Client Methods:** See `NurtureAPI.swift` (lines 300+)
- **Example App:** See `SwiftUI_Integration_Examples.swift`

---

## ✅ Checklist

Before shipping your iOS app:

- [ ] Replace `http://localhost:8000` with production URL
- [ ] Test with real Firebase authentication
- [ ] Handle token refresh
- [ ] Test all 40 endpoints
- [ ] Test pagination (try limit=5)
- [ ] Test error cases (bad token, missing baby)
- [ ] Test date filtering (from_time, to_time)
- [ ] Test analytics endpoint
- [ ] Handle network timeouts gracefully
- [ ] Test in both light and dark mode
- [ ] Test on different device sizes

---

## 🎯 Next Steps

1. Copy the 3 files to your Xcode project
2. Update base URL
3. Update your App.swift
4. Implement Firebase login
5. Start using the API!

Need help? Check:
- `iOS_API_REFERENCE.md` for endpoint details
- `SwiftUI_Integration_Examples.swift` for complete example code
- `NurtureAPI.swift` for all available methods

---

**Ready to integrate? All 40 endpoints are now in your hands! 🚀**
