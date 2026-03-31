# UI & Dashboard Specification
## Complete Component & Dashboard Implementation Guide

---

## 📋 Document Information

- **Product:** AI Marketing Automation Platform
- **Document Type:** UI/Dashboard Specification
- **Framework:** React + Tailwind CSS
- **Last Updated:** 2025-02-16
- **Status:** Implementation Ready

---

## 🎨 Dashboard Layouts by Role

### Layout Structure

```
┌─────────────────────────────────────────────────┐
│  Sidebar (260px)  │   Main Content Area       │
│                   │                             │
│  - Logo           │  ┌─────────────────────┐  │
│  - Navigation     │  │ Top Bar (64px)      │  │
│  - Quick Actions  │  ├─────────────────────┤  │
│  - User Menu      │  │                     │  │
│                   │  │ Page Content        │  │
│                   │  │                     │  │
│                   │  │                     │  │
│                   │  └─────────────────────┘  │
└─────────────────────────────────────────────────┘
```

---

## 📱 1. Dashboard Home Page

### Owner/Admin View

```typescript
// Dashboard.tsx
import React from 'react';
import { StatsCard, PerformanceChart, TopPosts, AIInsights } from '@/components';

const Dashboard: React.FC = () => {
  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-600 mt-1">Last 30 days overview</p>
        </div>
        <button className="btn-primary">
          Generate Content
        </button>
      </div>

      {/* Stats Cards Row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <StatsCard
          label="Total Reach"
          value="125,231"
          change="+15.3%"
          trend="up"
          icon="users"
        />
        <StatsCard
          label="Engagement"
          value="8,547"
          change="+23.1%"
          trend="up"
          icon="heart"
        />
        <StatsCard
          label="Engagement Rate"
          value="6.8%"
          change="+2.1%"
          trend="up"
          icon="trending-up"
        />
        <StatsCard
          label="New Followers"
          value="1,245"
          change="+32.5%"
          trend="up"
          icon="user-plus"
        />
      </div>

      {/* Performance Chart */}
      <div className="bg-white rounded-lg shadow-sm p-6">
        <h2 className="text-xl font-semibold mb-4">Performance Over Time</h2>
        <PerformanceChart />
      </div>

      {/* Two Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Performing Posts */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold">Top Posts</h2>
            <a href="/analytics" className="text-primary-600 text-sm">View All →</a>
          </div>
          <TopPosts limit={5} />
        </div>

        {/* AI Insights */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-xl font-semibold mb-4">AI Insights</h2>
          <AIInsights />
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <QuickAction
          icon="calendar"
          title="Content Calendar"
          description="View and manage scheduled posts"
          href="/calendar"
        />
        <QuickAction
          icon="plus"
          title="Generate Content"
          description="Create new posts with AI"
          href="/content/create"
        />
        <QuickAction
          icon="bar-chart"
          title="View Analytics"
          description="Deep dive into performance"
          href="/analytics"
        />
      </div>
    </div>
  );
};
```

### Viewer View (Limited)

```typescript
const DashboardViewer: React.FC = () => {
  return (
    <div className="p-6 space-y-6">
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <p className="text-blue-800">
          👁️ You have view-only access. Contact your admin to request edit permissions.
        </p>
      </div>

      {/* Same stats cards - read-only */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <StatsCard /* ... */ />
      </div>

      {/* Chart without edit controls */}
      <div className="bg-white rounded-lg shadow-sm p-6">
        <PerformanceChart readOnly />
      </div>
    </div>
  );
};
```

---

## 📊 2. Stats Card Component

### Implementation

```typescript
// components/dashboard/StatsCard.tsx
interface StatsCardProps {
  label: string;
  value: string | number;
  change?: string;
  trend?: 'up' | 'down' | 'neutral';
  icon?: string;
  loading?: boolean;
}

export const StatsCard: React.FC<StatsCardProps> = ({
  label,
  value,
  change,
  trend = 'neutral',
  icon,
  loading = false
}) => {
  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow-sm p-6 animate-pulse">
        <div className="h-4 bg-gray-200 rounded w-3/4 mb-4"></div>
        <div className="h-8 bg-gray-200 rounded w-1/2"></div>
      </div>
    );
  }

  const trendColors = {
    up: 'text-green-600 bg-green-50',
    down: 'text-red-600 bg-red-50',
    neutral: 'text-gray-600 bg-gray-50'
  };

  const trendIcons = {
    up: '↑',
    down: '↓',
    neutral: '→'
  };

  return (
    <div className="bg-white rounded-lg shadow-sm p-6 hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between mb-2">
        <p className="text-sm text-gray-600 font-medium">{label}</p>
        {icon && (
          <div className="w-10 h-10 rounded-full bg-primary-50 flex items-center justify-center">
            <Icon name={icon} className="w-5 h-5 text-primary-600" />
          </div>
        )}
      </div>
      
      <p className="text-3xl font-bold text-gray-900 mb-1">{value}</p>
      
      {change && (
        <div className="flex items-center gap-1">
          <span className={`text-xs font-medium px-2 py-1 rounded ${trendColors[trend]}`}>
            {trendIcons[trend]} {change}
          </span>
          <span className="text-xs text-gray-500">vs last period</span>
        </div>
      )}
    </div>
  );
};
```

---

## 📅 3. Content Calendar Page

### Calendar Layout

```typescript
// pages/Calendar.tsx
import { Calendar, momentLocalizer } from 'react-big-calendar';
import moment from 'moment';
import 'react-big-calendar/lib/css/react-big-calendar.css';

const localizer = momentLocalizer(moment);

const CalendarPage: React.FC = () => {
  const [view, setView] = useState<'month' | 'week'>('month');
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [posts, setPosts] = useState([]);

  const events = posts.map(post => ({
    id: post.id,
    title: post.content.substring(0, 50) + '...',
    start: new Date(post.scheduled_at),
    end: new Date(post.scheduled_at),
    resource: post
  }));

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Content Calendar</h1>
          <p className="text-gray-600 mt-1">Plan and schedule your content</p>
        </div>
        
        <div className="flex gap-3">
          <button className="btn-secondary">
            Auto-Schedule
          </button>
          <button className="btn-primary">
            + New Post
          </button>
        </div>
      </div>

      {/* View Selector */}
      <div className="flex gap-2">
        <button
          onClick={() => setView('week')}
          className={`px-4 py-2 rounded-md ${
            view === 'week' ? 'bg-primary-600 text-white' : 'bg-gray-100'
          }`}
        >
          Week
        </button>
        <button
          onClick={() => setView('month')}
          className={`px-4 py-2 rounded-md ${
            view === 'month' ? 'bg-primary-600 text-white' : 'bg-gray-100'
          }`}
        >
          Month
        </button>
      </div>

      {/* Calendar */}
      <div className="bg-white rounded-lg shadow-sm p-6">
        <Calendar
          localizer={localizer}
          events={events}
          startAccessor="start"
          endAccessor="end"
          view={view}
          onView={setView}
          date={selectedDate}
          onNavigate={setSelectedDate}
          onSelectEvent={handleEventClick}
          onSelectSlot={handleSlotClick}
          selectable
          className="h-[600px]"
          eventPropGetter={eventStyleGetter}
        />
      </div>

      {/* Selected Post Modal */}
      {selectedPost && (
        <PostPreviewModal
          post={selectedPost}
          onClose={() => setSelectedPost(null)}
          onEdit={handleEdit}
          onDelete={handleDelete}
        />
      )}
    </div>
  );
};

// Custom event styling
const eventStyleGetter = (event: any) => {
  const status = event.resource.status;
  
  const styles: Record<string, any> = {
    published: { backgroundColor: '#10b981', borderColor: '#059669' },
    scheduled: { backgroundColor: '#3b82f6', borderColor: '#2563eb' },
    draft: { backgroundColor: '#6b7280', borderColor: '#4b5563' },
    failed: { backgroundColor: '#ef4444', borderColor: '#dc2626' }
  };

  return {
    style: styles[status] || styles.draft
  };
};
```

---

## ✍️ 4. Content Editor

### Editor Component

```typescript
// components/content/ContentEditor.tsx
interface ContentEditorProps {
  post?: Post;
  onSave: (data: PostData) => void;
  onCancel: () => void;
}

export const ContentEditor: React.FC<ContentEditorProps> = ({
  post,
  onSave,
  onCancel
}) => {
  const [content, setContent] = useState(post?.content || '');
  const [platforms, setPlatforms] = useState<string[]>(post?.platforms || []);
  const [hashtags, setHashtags] = useState<string[]>(post?.hashtags || []);
  const [mediaUrls, setMediaUrls] = useState<string[]>(post?.media_urls || []);
  const [scheduledAt, setScheduledAt] = useState<Date | null>(post?.scheduled_at || null);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Editor Panel */}
      <div className="space-y-6">
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-xl font-semibold mb-4">Content</h2>
          
          {/* AI Generate Button */}
          <button
            onClick={handleAIGenerate}
            className="btn-secondary w-full mb-4"
          >
            <Sparkles className="w-4 h-4 mr-2" />
            Generate with AI
          </button>

          {/* Textarea */}
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="What do you want to share?"
            className="w-full h-48 p-4 border border-gray-300 rounded-lg resize-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          />
          
          <div className="flex justify-between items-center mt-2 text-sm text-gray-500">
            <span>{content.length} characters</span>
            <span>{getHashtagCount(content)} hashtags</span>
          </div>
        </div>

        {/* Media Upload */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-xl font-semibold mb-4">Media</h2>
          
          <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
            <ImagePlus className="w-12 h-12 mx-auto text-gray-400 mb-2" />
            <p className="text-gray-600 mb-2">Drop images here or click to upload</p>
            <p className="text-sm text-gray-500">PNG, JPG up to 5MB</p>
            
            <input
              type="file"
              multiple
              accept="image/*"
              onChange={handleMediaUpload}
              className="hidden"
              id="media-upload"
            />
            <label htmlFor="media-upload" className="btn-secondary mt-4 cursor-pointer">
              Choose Files
            </label>
          </div>

          {/* Media Preview */}
          {mediaUrls.length > 0 && (
            <div className="grid grid-cols-3 gap-4 mt-4">
              {mediaUrls.map((url, index) => (
                <div key={index} className="relative group">
                  <img src={url} className="rounded-lg w-full h-24 object-cover" />
                  <button
                    onClick={() => removeMedia(index)}
                    className="absolute top-2 right-2 bg-red-600 text-white rounded-full p-1 opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Hashtags */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-xl font-semibold mb-4">Hashtags</h2>
          
          <div className="flex flex-wrap gap-2 mb-3">
            {hashtags.map((tag, index) => (
              <span key={index} className="bg-primary-100 text-primary-700 px-3 py-1 rounded-full text-sm flex items-center gap-1">
                #{tag}
                <button onClick={() => removeHashtag(index)}>
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}
          </div>

          <input
            type="text"
            placeholder="Add hashtag..."
            onKeyDown={handleHashtagAdd}
            className="input-field"
          />
          
          <button onClick={handleSuggestHashtags} className="btn-secondary mt-2">
            Suggest Hashtags
          </button>
        </div>

        {/* Platform Selection */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-xl font-semibold mb-4">Platforms</h2>
          
          <div className="space-y-3">
            {availablePlatforms.map(platform => (
              <label key={platform.type} className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={platforms.includes(platform.type)}
                  onChange={() => togglePlatform(platform.type)}
                  className="w-5 h-5 rounded text-primary-600 focus:ring-primary-500"
                />
                <img src={platform.icon} className="w-6 h-6" />
                <span className="font-medium">{platform.name}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Schedule */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-xl font-semibold mb-4">Schedule</h2>
          
          <div className="space-y-4">
            <label className="flex items-center gap-3">
              <input
                type="radio"
                name="schedule"
                checked={!scheduledAt}
                onChange={() => setScheduledAt(null)}
              />
              <span>Publish now</span>
            </label>
            
            <label className="flex items-center gap-3">
              <input
                type="radio"
                name="schedule"
                checked={!!scheduledAt}
                onChange={() => setScheduledAt(new Date())}
              />
              <span>Schedule for later</span>
            </label>

            {scheduledAt && (
              <div className="ml-7">
                <DateTimePicker
                  value={scheduledAt}
                  onChange={setScheduledAt}
                  minDate={new Date()}
                />
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Preview Panel */}
      <div className="space-y-6">
        <div className="bg-white rounded-lg shadow-sm p-6 sticky top-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold">Preview</h2>
            <select 
              value={previewPlatform}
              onChange={(e) => setPreviewPlatform(e.target.value)}
              className="input-field w-auto"
            >
              {platforms.map(p => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </div>

          <div className="border border-gray-200 rounded-lg p-4">
            <PlatformPreview
              platform={previewPlatform}
              content={content}
              mediaUrls={mediaUrls}
              hashtags={hashtags}
            />
          </div>

          {/* Action Buttons */}
          <div className="flex gap-3 mt-6">
            <button onClick={onCancel} className="btn-secondary flex-1">
              Cancel
            </button>
            <button onClick={handleSaveDraft} className="btn-secondary flex-1">
              Save Draft
            </button>
            <button onClick={handlePublish} className="btn-primary flex-1">
              {scheduledAt ? 'Schedule' : 'Publish'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
```

---

## 📈 5. Analytics Dashboard

### Analytics Layout

```typescript
// pages/Analytics.tsx
const AnalyticsPage: React.FC = () => {
  const [dateRange, setDateRange] = useState<DateRange>({
    start: subDays(new Date(), 30),
    end: new Date()
  });

  return (
    <div className="p-6 space-y-6">
      {/* Header with Date Range Picker */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Analytics</h1>
          <p className="text-gray-600 mt-1">Track your performance</p>
        </div>
        
        <DateRangePicker
          value={dateRange}
          onChange={setDateRange}
        />
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <StatsCard label="Total Reach" value="125,231" change="+15.3%" trend="up" />
        <StatsCard label="Engagement" value="8,547" change="+23.1%" trend="up" />
        <StatsCard label="Engagement Rate" value="6.8%" change="+2.1%" trend="up" />
        <StatsCard label="Followers" value="12,450" change="+1,245" trend="up" />
      </div>

      {/* Performance Chart */}
      <div className="bg-white rounded-lg shadow-sm p-6">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-semibold">Performance Trends</h2>
          
          <div className="flex gap-2">
            <button className="btn-secondary">Day</button>
            <button className="btn-primary">Week</button>
            <button className="btn-secondary">Month</button>
          </div>
        </div>

        <LineChart
          data={performanceData}
          xAxis="date"
          yAxis={["reach", "engagement"]}
          height={400}
        />
      </div>

      {/* Platform Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Platform Performance */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-xl font-semibold mb-4">Platform Performance</h2>
          
          <div className="space-y-4">
            {platformStats.map(platform => (
              <div key={platform.type} className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <img src={platform.icon} className="w-8 h-8" />
                  <div>
                    <p className="font-medium">{platform.name}</p>
                    <p className="text-sm text-gray-500">{platform.posts} posts</p>
                  </div>
                </div>
                
                <div className="text-right">
                  <p className="font-semibold">{platform.reach.toLocaleString()}</p>
                  <p className="text-sm text-gray-500">reach</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Engagement Breakdown */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-xl font-semibold mb-4">Engagement Breakdown</h2>
          
          <DonutChart
            data={[
              { label: 'Likes', value: 5200, color: '#3b82f6' },
              { label: 'Comments', value: 1800, color: '#10b981' },
              { label: 'Shares', value: 1200, color: '#f59e0b' },
              { label: 'Saves', value: 347, color: '#8b5cf6' }
            ]}
          />
        </div>
      </div>

      {/* Top Content */}
      <div className="bg-white rounded-lg shadow-sm p-6">
        <h2 className="text-xl font-semibold mb-4">Top Performing Posts</h2>
        
        <div className="space-y-4">
          {topPosts.map(post => (
            <div key={post.id} className="flex gap-4 p-4 border border-gray-200 rounded-lg hover:shadow-md transition-shadow">
              {post.media_urls[0] && (
                <img src={post.media_urls[0]} className="w-20 h-20 rounded object-cover" />
              )}
              
              <div className="flex-1">
                <p className="text-sm text-gray-900 line-clamp-2">{post.content}</p>
                <p className="text-xs text-gray-500 mt-1">
                  {format(post.published_at, 'MMM d, yyyy')}
                </p>
              </div>

              <div className="flex gap-6 text-center">
                <div>
                  <p className="text-lg font-semibold">{post.reach.toLocaleString()}</p>
                  <p className="text-xs text-gray-500">Reach</p>
                </div>
                <div>
                  <p className="text-lg font-semibold">{post.engagement.toLocaleString()}</p>
                  <p className="text-xs text-gray-500">Engagement</p>
                </div>
                <div>
                  <p className="text-lg font-semibold">{post.engagement_rate}%</p>
                  <p className="text-xs text-gray-500">Rate</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Export Report */}
      <div className="flex justify-center">
        <button className="btn-secondary">
          <Download className="w-4 h-4 mr-2" />
          Export Report (PDF)
        </button>
      </div>
    </div>
  );
};
```

---

## 🔔 6. Notification System

### Notification Dropdown

```typescript
// components/layout/NotificationDropdown.tsx
export const NotificationDropdown: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const { notifications, unreadCount, markAsRead } = useNotifications();

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 rounded-full hover:bg-gray-100"
      >
        <Bell className="w-6 h-6 text-gray-600" />
        {unreadCount > 0 && (
          <span className="absolute top-0 right-0 bg-red-600 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
            {unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-80 bg-white rounded-lg shadow-xl border border-gray-200 z-50">
          <div className="p-4 border-b border-gray-200 flex justify-between items-center">
            <h3 className="font-semibold">Notifications</h3>
            {unreadCount > 0 && (
              <button
                onClick={markAllAsRead}
                className="text-xs text-primary-600 hover:underline"
              >
                Mark all as read
              </button>
            )}
          </div>

          <div className="max-h-96 overflow-y-auto">
            {notifications.length === 0 ? (
              <div className="p-8 text-center text-gray-500">
                <Bell className="w-12 h-12 mx-auto mb-2 text-gray-300" />
                <p>No notifications yet</p>
              </div>
            ) : (
              notifications.map(notif => (
                <div
                  key={notif.id}
                  className={`p-4 border-b border-gray-100 hover:bg-gray-50 cursor-pointer ${
                    !notif.is_read ? 'bg-blue-50' : ''
                  }`}
                  onClick={() => handleNotificationClick(notif)}
                >
                  <div className="flex gap-3">
                    <NotificationIcon type={notif.type} />
                    <div className="flex-1">
                      <p className="font-medium text-sm">{notif.title}</p>
                      <p className="text-xs text-gray-600 mt-1">{notif.message}</p>
                      <p className="text-xs text-gray-400 mt-2">
                        {formatDistanceToNow(notif.created_at, { addSuffix: true })}
                      </p>
                    </div>
                    {!notif.is_read && (
                      <div className="w-2 h-2 bg-blue-600 rounded-full"></div>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="p-2 border-t border-gray-200">
            <a href="/notifications" className="block text-center text-sm text-primary-600 hover:underline py-2">
              View all notifications
            </a>
          </div>
        </div>
      )}
    </div>
  );
};
```

---

## ⚙️ 7. Settings Page

### Settings Layout

```typescript
// pages/Settings.tsx
const SettingsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState('account');

  return (
    <div className="p-6">
      <h1 className="text-3xl font-bold text-gray-900 mb-6">Settings</h1>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Sidebar Navigation */}
        <div className="lg:col-span-1">
          <nav className="space-y-1">
            {settingsTabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`w-full text-left px-4 py-3 rounded-lg flex items-center gap-3 ${
                  activeTab === tab.id
                    ? 'bg-primary-50 text-primary-700 font-medium'
                    : 'text-gray-700 hover:bg-gray-50'
                }`}
              >
                <tab.icon className="w-5 h-5" />
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        {/* Settings Content */}
        <div className="lg:col-span-3">
          {activeTab === 'account' && <AccountSettings />}
          {activeTab === 'team' && <TeamSettings />}
          {activeTab === 'platforms' && <PlatformSettings />}
          {activeTab === 'billing' && <BillingSettings />}
          {activeTab === 'notifications' && <NotificationSettings />}
        </div>
      </div>
    </div>
  );
};

// Account Settings Tab
const AccountSettings: React.FC = () => (
  <div className="space-y-6">
    <div className="bg-white rounded-lg shadow-sm p-6">
      <h2 className="text-xl font-semibold mb-4">Profile Information</h2>
      
      <form className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Full Name
          </label>
          <input type="text" className="input-field" defaultValue="John Doe" />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Email
          </label>
          <input type="email" className="input-field" defaultValue="john@example.com" />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Phone
          </label>
          <input type="tel" className="input-field" defaultValue="+1234567890" />
        </div>

        <button type="submit" className="btn-primary">
          Save Changes
        </button>
      </form>
    </div>

    <div className="bg-white rounded-lg shadow-sm p-6">
      <h2 className="text-xl font-semibold mb-4">Change Password</h2>
      
      <form className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Current Password
          </label>
          <input type="password" className="input-field" />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            New Password
          </label>
          <input type="password" className="input-field" />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Confirm New Password
          </label>
          <input type="password" className="input-field" />
        </div>

        <button type="submit" className="btn-primary">
          Update Password
        </button>
      </form>
    </div>

    <div className="bg-white rounded-lg shadow-sm p-6 border-red-200">
      <h2 className="text-xl font-semibold text-red-600 mb-4">Danger Zone</h2>
      
      <p className="text-sm text-gray-600 mb-4">
        Once you delete your account, there is no going back. Please be certain.
      </p>

      <button className="btn-danger">
        Delete Account
      </button>
    </div>
  </div>
);
```

---

## 🎨 8. Reusable Components

### Button Component

```typescript
// components/ui/Button.tsx
type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost';
type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  icon?: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  loading = false,
  icon,
  children,
  className = '',
  disabled,
  ...props
}) => {
  const baseClasses = 'inline-flex items-center justify-center font-medium rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2';
  
  const variantClasses = {
    primary: 'bg-primary-600 text-white hover:bg-primary-700 focus:ring-primary-500 disabled:bg-primary-300',
    secondary: 'bg-gray-100 text-gray-900 hover:bg-gray-200 focus:ring-gray-500 disabled:bg-gray-100',
    danger: 'bg-red-600 text-white hover:bg-red-700 focus:ring-red-500 disabled:bg-red-300',
    ghost: 'bg-transparent text-gray-700 hover:bg-gray-100 focus:ring-gray-500'
  };

  const sizeClasses = {
    sm: 'px-3 py-1.5 text-sm',
    md: 'px-4 py-2 text-base',
    lg: 'px-6 py-3 text-lg'
  };

  return (
    <button
      className={`${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <Loader className="animate-spin w-4 h-4 mr-2" />}
      {!loading && icon && <span className="mr-2">{icon}</span>}
      {children}
    </button>
  );
};
```

### Modal Component

```typescript
// components/ui/Modal.tsx
interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  closeOnOverlayClick?: boolean;
}

export const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  children,
  size = 'md',
  closeOnOverlayClick = true
}) => {
  if (!isOpen) return null;

  const sizeClasses = {
    sm: 'max-w-md',
    md: 'max-w-lg',
    lg: 'max-w-2xl',
    xl: 'max-w-4xl'
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen px-4">
        {/* Overlay */}
        <div
          className="fixed inset-0 bg-black bg-opacity-50 transition-opacity"
          onClick={closeOnOverlayClick ? onClose : undefined}
        />

        {/* Modal */}
        <div className={`relative bg-white rounded-lg shadow-xl ${sizeClasses[size]} w-full`}>
          {/* Header */}
          {title && (
            <div className="flex items-center justify-between p-6 border-b border-gray-200">
              <h2 className="text-xl font-semibold">{title}</h2>
              <button
                onClick={onClose}
                className="text-gray-400 hover:text-gray-600 transition-colors"
              >
                <X className="w-6 h-6" />
              </button>
            </div>
          )}

          {/* Content */}
          <div className="p-6">
            {children}
          </div>
        </div>
      </div>
    </div>
  );
};
```

---

## ✅ UI Implementation Checklist

### Core Pages
- [ ] Dashboard (all role variants)
- [ ] Content Calendar
- [ ] Content Editor
- [ ] Analytics
- [ ] Settings
- [ ] Team Management

### Components
- [ ] StatsCard
- [ ] Button
- [ ] Modal
- [ ] Dropdown
- [ ] DatePicker
- [ ] Charts (Line, Donut, Bar)
- [ ] PlatformPreview
- [ ] NotificationDropdown

### Layouts
- [ ] Sidebar Navigation
- [ ] Top Bar
- [ ] Mobile Navigation
- [ ] Empty States
- [ ] Loading States
- [ ] Error States

### Role-Based Views
- [ ] Owner/Admin full access
- [ ] Manager limited access
- [ ] Editor content-only access
- [ ] Viewer read-only access

### Responsive Design
- [ ] Mobile (320px+)
- [ ] Tablet (768px+)
- [ ] Desktop (1024px+)
- [ ] Wide (1440px+)

---

**UI Status:** Implementation Ready  
**Next Steps:** Build components → Integrate with API → Test responsiveness  
**Review:** Before production deployment
