# Frontend Structure & UX/UI Overview

## **1. Application Structure**
The application is a **single-page** standard HTML/CSS/JS web app served via FastAPI templates.
- **Entry Point**: `templates/index.html`
- **Styling**: Vanilla CSS (embedded in `<style>`).
- **State Management**: Local JavaScript object `state` synced with the backend via API calls.

---

## **2. User Interface (UI) Components**
The UI consists of 3 main views, toggled via display properties:
1.  **Loading Screen** (`#loadingRoot`): Spinner shown during async operations.
2.  **Home Screen** (`#homeRoot`): Landing page with a "Create New Bill Link" button.
3.  **App Screen** (`#appRoot`): The main workspace, divided into 5 sections.


### **Main Workspace Sections**
| Section | ID | Description |
| :--- | :--- | :--- |
| **Header** | N/A | Contains "Bill Name" input, "New Bill" and "Copy Link" buttons. <br> **Features**: <br> - **Bill Name**: Visual-only text input (default: "My Bill") to label the session. <br> - **New Bill**: Forks the current state into a new session. <br> - **Copy Link**: Copies the current session URL to clipboard. <br> *Note: Manual "Save" and "Refresh" buttons have been removed.* |
| **1. Consumption** | `#s1` | Matrix table for Dishes/People inputs. **Features**: Color-coded person names in headers. |
| **2. Who Paid?** | `#s2` | List of payers. **Features**: Color-coded bold names in dropdowns, shortcuts for "All" or "Max". |
| **3. Who is Covering?** | `#s3` | List of covers. **Features**: Color-coded bold names in dropdowns. |
| **4. Settlement** | `#s4` | "Calculate Settlements" button and the results list showing who owes whom. |
| **5. Data** | `#s5` | JSON dump/load area for debugging or manual backup. |

### **General Features**
- **Live Warning System**: 
    - Automatically checks difference between Total Bill (Section 1) and Total Paid (Section 2).
    - If difference > 0.1, displays a warning in Section 2.
    - **Blocks Calculation**: Disables the "Calculate Settlements" button until the discrepancy is resolved.
- **Default Initialization**: New sessions start with Person 1 automatically added as a payer with 0 amount.

### **Detailed Section Features**

### 2. Who Paid? (Payments)
- **Input**: List of people who paid for the meal.
- **Default**: Person 1 is auto-added.
- **Components**:
    - **Payer Select**: Dropdown with colored names.
    - **Amount Input**: Number field.
    - **"All" Button**: Sets amount to the total bill.
    - **"Max" Button**: Sets amount to remaining unpaid balance.
- **Validation**: Live check against total bill cost.

### 3. Who is Covering? (Covers)
- **Features**: Color-coded bold names in dropdowns.

---

## **3. User Experience (UX) Flow**

### **Session Management**
- **New User**: Starts at Home -> Clicks "Create New Bill Link" -> `POST /sessions` -> Redirects to App with `?id=...`.
- **Existing Link**: User creates/visits link with `?id={uuid}` -> App loads session data via `GET /sessions/{id}` -> Renders App views.
- **Auto-Save**: Any change to data models (dishes, people, ratios, payments) triggers an `autoSave()` function (debounced 1s) to `PUT /sessions/{id}`.

### **Core Workflows**
1.  **Adding Data**:
    - Users add dishes and people in Section 1.
    - Matrix cells (`modRatio`) increment/decrement consumption.
    - **Input Validation & UX for Section 1 (Consumption)**:
        - **Dish Name**: 
            - Textarea with 2-line visual limit (27px).
            - Auto-shrinks font size (12px -> 9px) to fit text.
        - **Dish Price**: Number input.
        - **Ratio Matrix**:
            - **Input**: Direct numeric input (sanitized to allow ONLY digits and one decimal).
            - **Buttons**: +/- buttons that snap decimals to nearest integer.
            - **Visuals**: Dynamic contrast (Gray for 0, Black for >0), persistent border indicator.
        - **Add Dish**: Adds a new row and **auto-scrolls** the window down by one row height to keep the button under the cursor.
2.  **Calculations**:
    - Users enter payment info in Section 2.
    - Clicks "Calculate Settlements" in Section 4.
    - UI validates `Total Dish Cost` vs. `Total Paid`. Warnings shown if mismatch > 0.1.
3.  **Settlement**:
    - Displays a list of debts (e.g., "Alice pays Bob $50").
    - Users can add bank details/notes for creditors (synced across all debts to that creditor).

---

## **4. API Interactions**

### **Backend Endpoints Used**

| Method | Endpoint | Payload / Params | Functionality |
| :--- | :--- | :--- | :--- |
| **POST** | `/sessions` | `{ state: {...} }` | Creates a new session. Returns `{ id: "..." }`. |
| **GET** | `/sessions/{id}` | N/A | Fetch session state. Returns `{ id, state }`. |
| **PUT** | `/sessions/{id}` | `{ state: {...} }` | Updates/Saves session state. |
| **POST** | `/calculate` | `{ section1: {...}, payments: [...], covers: [...] }` | Performs split logic. Returns `{ settlements: [...] }`. |

### **Data Models (Frontend `state`)**
```javascript
let state = {
    people: [{id, name}, ...],
    dishes: [{id, name, price}, ...],
    ratios: { personId: { dishId: number } },
    paymentDetails: { personId: "note" },
    colors: { personId: { bg: "hex", text: "hex" } },
    payments: [{person_id, amount}],
    covers: [{person_id, amount}]
};
```
