# Analytics Dashboard Design - Subject-Based System

## 🎯 Recommended Approach: **Subject-Based System**

### Why Subject-Based?
1. **Realistic**: Matches real educational institutions
2. **Scalable**: Works with multiple teachers and many students
3. **Organized**: Videos grouped by subject/topic
4. **Flexible**: Students can enroll in multiple subjects
5. **Clear Analytics**: Teachers see progress per subject

---

## 📊 Database Schema

### New Tables Needed:

```sql
-- 1. Subjects Table
CREATE TABLE subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,                    -- e.g., "Mathematics", "Physics"
    description TEXT,                      -- Subject description
    created_by INTEGER NOT NULL,           -- Teacher who created it
    created_at TEXT NOT NULL,
    FOREIGN KEY(created_by) REFERENCES users(id)
);

-- 2. Teacher-Subject Assignment (Many-to-Many)
CREATE TABLE teacher_subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id INTEGER NOT NULL,
    subject_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(teacher_id) REFERENCES users(id),
    FOREIGN KEY(subject_id) REFERENCES subjects(id),
    UNIQUE(teacher_id, subject_id)  -- One teacher can't be assigned twice to same subject
);

-- 3. Student Enrollment (Many-to-Many)
CREATE TABLE student_subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    subject_id INTEGER NOT NULL,
    enrolled_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',  -- active/inactive
    FOREIGN KEY(student_id) REFERENCES users(id),
    FOREIGN KEY(subject_id) REFERENCES subjects(id),
    UNIQUE(student_id, subject_id)  -- One student can't enroll twice in same subject
);

-- 4. Modify existing contents table
ALTER TABLE contents ADD COLUMN title TEXT;
ALTER TABLE contents ADD COLUMN subject_id INTEGER;
ALTER TABLE contents ADD FOREIGN KEY(subject_id) REFERENCES subjects(id);

-- 5. Video Watch History (Progress Tracking)
CREATE TABLE video_watch_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    video_id INTEGER NOT NULL,             -- References contents.id
    subject_id INTEGER,                     -- For quick filtering
    watch_duration REAL DEFAULT 0,         -- Seconds watched
    total_duration REAL,                    -- Total video duration
    last_watched_at TEXT NOT NULL,
    completed INTEGER DEFAULT 0,            -- 0 = not completed, 1 = completed
    language_used TEXT,                     -- Which translation language they used
    FOREIGN KEY(student_id) REFERENCES users(id),
    FOREIGN KEY(video_id) REFERENCES contents(id),
    FOREIGN KEY(subject_id) REFERENCES subjects(id)
);
```

---

## 🔄 Workflow

### For Teachers:
1. **Create Subject**: Teacher creates a subject (e.g., "Mathematics Grade 10")
2. **Upload Videos**: Upload videos and assign to subject
3. **View Analytics**: See all students enrolled in their subjects and their progress

### For Students:
1. **Browse Subjects**: See all available subjects
2. **Enroll**: Self-enroll in subjects they want to study
3. **Watch Videos**: Watch videos in enrolled subjects
4. **Progress Tracked**: System automatically tracks their watch history

---

## 📈 Analytics Dashboard Features

### Teacher Dashboard Shows:

1. **Subject Overview**
   - Total students enrolled per subject
   - Total videos per subject
   - Average completion rate

2. **Student Progress Table**
   - Student name, email
   - Videos watched / Total videos
   - Completion percentage
   - Last activity date
   - Preferred language (most used translation)

3. **Video Analytics**
   - Most watched videos
   - Least watched videos
   - Average watch duration per video
   - Completion rate per video

4. **Language Usage**
   - Which languages students prefer for translations
   - Most popular translation languages per subject

---

## 🎨 UI Flow

### Teacher Side:
```
Dashboard → My Subjects → [Select Subject] → Analytics
  - Student List with Progress
  - Video Performance
  - Language Statistics
```

### Student Side:
```
Home → Browse Subjects → [Enroll] → My Subjects → Watch Videos
```

---

## 💡 Implementation Priority

### Phase 1 (Core):
1. ✅ Database schema (subjects, enrollments, watch history)
2. ✅ Subject creation (teachers)
3. ✅ Subject enrollment (students)
4. ✅ Video assignment to subjects
5. ✅ Watch history tracking

### Phase 2 (Analytics):
1. ✅ Basic analytics dashboard
2. ✅ Student progress table
3. ✅ Video performance metrics

### Phase 3 (Advanced):
1. Export analytics to CSV/PDF
2. Email notifications for teachers
3. Student progress reports

---

## 🔐 Access Control

- **Teachers**: Can only see analytics for subjects they're assigned to
- **Students**: Can only enroll in subjects (self-service)
- **Admin** (future): Can see all analytics

---

## 📝 Example Queries

### Get all students in teacher's subjects:
```sql
SELECT DISTINCT u.id, u.email, u.username
FROM users u
JOIN student_subjects ss ON u.id = ss.student_id
JOIN teacher_subjects ts ON ss.subject_id = ts.subject_id
WHERE ts.teacher_id = ? AND u.role = 'student'
```

### Get student progress for a subject:
```sql
SELECT 
    c.id as video_id,
    c.title,
    vwh.watch_duration,
    vwh.total_duration,
    vwh.completed,
    vwh.last_watched_at,
    vwh.language_used
FROM contents c
LEFT JOIN video_watch_history vwh ON c.id = vwh.video_id AND vwh.student_id = ?
WHERE c.subject_id = ?
ORDER BY c.created_at
```

---

## 🚀 Next Steps

1. Implement database migrations
2. Add subject management endpoints
3. Add enrollment endpoints
4. Add watch history tracking
5. Build analytics dashboard UI
6. Test with sample data




