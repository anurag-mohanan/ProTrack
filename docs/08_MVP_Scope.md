# ProTrack MVP Scope

## Objective

Create a simple internal project tracking system for Prosohm to replace Excel-based tracking.

---

## Modules

### Users

Roles:

* Admin
* Project Manager
* Designer

---

### Customers

Fields:

* Customer Name
* Customer Code
* Address
* Active

---

### Customer Contacts

Fields:

* First Name
* Last Name
* Email
* Phone
* Job Title
* Primary Contact

---

### Projects

Fields:

* Tool Number
* Part Description
* Customer
* Customer Contact
* Designer
* Quoted Hours
* Due Date
* Status
* Notes

Project Status:

* Not Started
* In Progress
* Waiting For Customer
* Completed

---

### Milestones

Default Milestones:

* Feasibility
* Blockout
* Roughing
* Intermediate Review
* Final Review
* File Release
* BOM Release

Milestone Status:

* Not Started
* In Progress
* Completed
* N/A

---

### Timesheets

Fields:

* Date
* User
* Project
* Task Type
* Hours
* Description

---

### Dashboard

Metrics:

* Active Projects
* Projects Due This Week
* Overdue Projects
* Hours Logged This Month

---

## Out Of Scope

* Parent Projects
* Project Health
* Delay Reasons
* Milestone Templates
* Multiple Task Types Per Project
* Notifications
* Reporting Engine
* Customer Portal

These features will be considered after MVP completion.
