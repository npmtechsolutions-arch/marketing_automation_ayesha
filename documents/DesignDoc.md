# Design Document
## AI Marketing Automation Platform

---

## 📋 Document Information

- **Product Name:** AI Marketing Decision Engine
- **Design Version:** 1.0
- **Last Updated:** 2025-02-16
- **Design Lead:** [Name]
- **Status:** In Progress

---

## 🎨 Design Philosophy

### Core Principles

**1. Intelligence Made Visible**
- Show AI reasoning, don't hide it
- Explain "why" behind every recommendation
- Make the AI feel like a collaborator, not a black box

**2. Clarity Over Complexity**
- Every screen has one primary action
- Progressive disclosure of advanced features
- No marketing jargon - speak human

**3. Trust Through Transparency**
- Show confidence levels on AI suggestions
- Allow easy overrides and edits
- Display data sources clearly

**4. Speed Matters**
- Default to action, not configuration
- Minimize clicks to publish
- Smart defaults everywhere

**5. Professional Yet Approachable**
- Not sterile corporate software
- Not playful consumer app
- Sweet spot: Confident advisor

---

## 🎨 Visual Design System

### Color Palette

#### Primary Colors
```
Brand Primary (Purple/Blue):
- Primary 900: #1e1b4b (Deep Navy) - Headers, important text
- Primary 700: #4338ca (Rich Blue) - Primary CTA buttons
- Primary 500: #6366f1 (Brand Blue) - Links, accents
- Primary 300: #a5b4fc (Light Blue) - Hover states
- Primary 100: #e0e7ff (Pale Blue) - Backgrounds, cards
```

#### Neutral Colors
```
Grayscale:
- Gray 900: #111827 (Almost Black) - Body text
- Gray 700: #374151 (Dark Gray) - Secondary text
- Gray 500: #6b7280 (Medium Gray) - Placeholder text
- Gray 300: #d1d5db (Light Gray) - Borders
- Gray 100: #f3f4f6 (Very Light Gray) - Backgrounds
- White: #ffffff (Pure White) - Cards, modals
```

#### Semantic Colors
```
Success:
- Green 600: #059669 (Success actions, positive metrics)
- Green 100: #d1fae5 (Success backgrounds)

Warning:
- Amber 600: #d97706 (Alerts, cautions)
- Amber 100: #fef3c7 (Warning backgrounds)

Error:
- Red 600: #dc2626 (Errors, destructive actions)
- Red 100: #fee2e2 (Error backgrounds)

Info:
- Blue 600: #2563eb (Information, tips)
- Blue 100: #dbeafe (Info backgrounds)
```

#### Platform Colors (Social Media)
```
Used for platform badges and indicators:
- Facebook: #1877f2
- Instagram: #e4405f (gradient available)
- LinkedIn: #0a66c2
- Twitter/X: #000000
- YouTube: #ff0000
- TikTok: #000000
```

### Typography

#### Font Families
```
Primary Font (UI Text):
- Family: Inter
- Weights: 400 (Regular), 500 (Medium), 600 (Semi-Bold), 700 (Bold)
- Usage: All interface text, buttons, labels
- Fallback: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif

Secondary Font (Headings):
- Family: Plus Jakarta Sans
- Weights: 600 (Semi-Bold), 700 (Bold), 800 (Extra Bold)
- Usage: Page titles, section headers
- Fallback: Inter, sans-serif

Monospace (Code/Data):
- Family: JetBrains Mono
- Weight: 400 (Regular)
- Usage: API keys, code snippets, technical data
- Fallback: 'Courier New', monospace
```

#### Type Scale
```
Desktop:
- H1: 36px / 600 weight / 44px line-height (Page titles)
- H2: 30px / 600 weight / 38px line-height (Section headers)
- H3: 24px / 600 weight / 32px line-height (Card titles)
- H4: 20px / 600 weight / 28px line-height (Subsections)
- Body Large: 16px / 400 weight / 24px line-height (Primary text)
- Body: 14px / 400 weight / 20px line-height (Secondary text)
- Small: 12px / 400 weight / 16px line-height (Captions, labels)

Mobile:
- H1: 28px / 600 weight / 36px line-height
- H2: 24px / 600 weight / 32px line-height
- H3: 20px / 600 weight / 28px line-height
- Body Large: 16px / 400 weight / 24px line-height
- Body: 14px / 400 weight / 20px line-height
```

### Spacing System

```
Base Unit: 4px

Scale:
- 0: 0px
- 1: 4px (Tiny gaps)
- 2: 8px (Small gaps)
- 3: 12px (Default gaps)
- 4: 16px (Medium gaps)
- 5: 20px (Comfortable gaps)
- 6: 24px (Large gaps)
- 8: 32px (Section spacing)
- 10: 40px (Major section spacing)
- 12: 48px (Page-level spacing)
- 16: 64px (Hero spacing)

Common Patterns:
- Card padding: 24px (6 units)
- Button padding: 12px 24px (3 units vertical, 6 units horizontal)
- Section gap: 32px (8 units)
- Page margin: 24px mobile, 48px desktop
```

### Border Radius

```
- xs: 4px (Small elements, badges)
- sm: 6px (Buttons, inputs)
- md: 8px (Cards, small modals)
- lg: 12px (Large cards, major sections)
- xl: 16px (Hero sections, feature cards)
- 2xl: 24px (Modals, overlays)
- full: 9999px (Pills, circular avatars)
```

### Shadows

```
- None: No shadow
- xs: 0 1px 2px rgba(0,0,0,0.05) (Subtle lift)
- sm: 0 1px 3px rgba(0,0,0,0.1) (Default cards)
- md: 0 4px 6px rgba(0,0,0,0.1) (Hover states)
- lg: 0 10px 15px rgba(0,0,0,0.1) (Modals)
- xl: 0 20px 25px rgba(0,0,0,0.1) (Overlays)

Colored Shadows (for emphasis):
- Primary: 0 4px 14px rgba(99,102,241,0.25)
- Success: 0 4px 14px rgba(5,150,105,0.25)
```

---

## 🧩 Component Library

### Buttons

#### Primary Button
```
Purpose: Main call-to-action
Visual:
- Background: Primary 700 (#4338ca)
- Text: White
- Padding: 12px 24px
- Border radius: 6px
- Font: 14px, 600 weight
- Hover: Primary 800, shadow-md
- Active: Primary 900
- Disabled: Gray 300, cursor not-allowed

Examples:
"Generate Content", "Publish Now", "Connect Platform"
```

#### Secondary Button
```
Purpose: Alternative actions
Visual:
- Background: Transparent
- Border: 1px solid Primary 500
- Text: Primary 700
- Padding: 12px 24px
- Border radius: 6px
- Hover: Background Primary 50
- Active: Background Primary 100

Examples:
"Preview", "Edit", "Schedule Later"
```

#### Destructive Button
```
Purpose: Dangerous actions
Visual:
- Background: Red 600
- Text: White
- Padding: 12px 24px
- Hover: Red 700
- Requires confirmation for critical actions

Examples:
"Delete Campaign", "Disconnect Account"
```

#### Ghost Button
```
Purpose: Tertiary actions
Visual:
- Background: Transparent
- Text: Gray 700
- Padding: 12px 24px
- Hover: Background Gray 100

Examples:
"Cancel", "Skip", "Maybe Later"
```

### Input Fields

#### Text Input
```
Visual:
- Border: 1px solid Gray 300
- Background: White
- Padding: 12px 16px
- Border radius: 6px
- Font: 14px
- Focus: Border Primary 500, shadow-sm with primary color

States:
- Default: Gray border
- Focus: Primary border + glow
- Error: Red border, red text below
- Disabled: Gray 100 background, cursor not-allowed
```

#### Textarea
```
Same as text input but:
- Minimum height: 120px
- Resize: vertical only
- Max characters indicator when > 80% full
```

#### Select Dropdown
```
Visual:
- Same as text input
- Chevron icon on right
- Dropdown: White background, shadow-lg
- Options: Hover gray 100
- Multi-select: Show count badge
```

### Cards

#### Content Card
```
Purpose: Display generated posts, content items
Visual:
- Background: White
- Padding: 24px
- Border radius: 8px
- Shadow: sm
- Hover: shadow-md (lift effect)

Structure:
- Header: Platform icon + date/time
- Body: Content preview
- Footer: Edit, Delete, Schedule buttons
```

#### Stat Card
```
Purpose: Show metrics, analytics
Visual:
- Background: White
- Padding: 24px
- Border radius: 8px
- Shadow: sm

Structure:
- Icon (colored, 24x24px)
- Label (Gray 700, 14px)
- Value (Gray 900, 30px, 700 weight)
- Change indicator (+12% in green/red)
```

#### Strategy Card
```
Purpose: Display AI recommendations
Visual:
- Background: Primary 50
- Border: 1px solid Primary 200
- Padding: 24px
- Border radius: 8px
- Icon: Sparkles/Brain (AI indicator)

Structure:
- "AI Recommendation" badge
- Headline (Bold)
- Description
- CTA button
```

### Navigation

#### Sidebar Navigation
```
Width: 260px desktop, full-width mobile drawer
Background: Gray 900 (dark) or White (light)

Items:
- Icon + Label
- Active state: Primary 500 background
- Hover: Gray 700 background (dark mode)
- Badge for notifications

Sections:
- Logo at top
- Main navigation
- Secondary items
- User profile at bottom
```

#### Top Bar
```
Height: 64px
Background: White
Border bottom: 1px Gray 200

Left: Breadcrumbs or page title
Right: Notifications, user menu, settings

Mobile: Hamburger menu + logo + user avatar
```

### Modals

#### Standard Modal
```
Visual:
- Overlay: Black 50% opacity
- Container: White, shadow-xl
- Max width: 600px
- Border radius: 12px
- Padding: 32px

Structure:
- Close X (top right)
- Title (H3)
- Content area
- Footer with actions (right-aligned buttons)
```

#### Confirmation Modal
```
Smaller: Max width 400px
Icon at top (warning/info/success)
Clear Yes/No buttons
Destructive action button is red
```

### Toast Notifications

```
Position: Top right (desktop), top center (mobile)
Width: 360px
Background: White
Border: Left border (4px) in semantic color
Shadow: lg
Duration: 4 seconds (closable)

Variants:
- Success: Green border + checkmark icon
- Error: Red border + X icon
- Warning: Amber border + alert icon
- Info: Blue border + info icon
```

### Loading States

#### Skeleton Loading
```
Use for content cards, lists
- Animated gradient: Gray 200 to Gray 300
- Match shape of content being loaded
- Border radius: 4px
```

#### Spinner
```
Use for button states, small actions
- Size: 20px (default), 16px (small), 32px (large)
- Color: Primary 500 or White (on colored backgrounds)
- Animation: Smooth rotation
```

#### Progress Bar
```
Use for uploads, generation processes
- Height: 8px
- Background: Gray 200
- Fill: Primary 500
- Border radius: 4px
- Show percentage text above
```

### Badges

```
Small: 20px height, 8px padding horizontal
Medium: 24px height, 12px padding horizontal

Variants:
- Status: Gray (draft), Green (published), Yellow (scheduled)
- Platform: Use platform brand colors
- Count: Primary 500 background, white text
- New: Red background, white text
```

---

## 📱 Layout Structure

### Responsive Breakpoints

```
- Mobile: 0-640px
- Tablet: 641-1024px
- Desktop: 1025-1440px
- Wide: 1441px+

Grid System:
- Mobile: 4 columns, 16px gutter
- Tablet: 8 columns, 24px gutter
- Desktop: 12 columns, 32px gutter
```

### Page Layouts

#### Dashboard Layout
```
Desktop:
┌─────────────────────────────────────┐
│  Sidebar (260px)  │   Main Content  │
│                   │                 │
│  - Logo           │  - Top Bar      │
│  - Nav Items      │  - Page Content │
│  - User Menu      │                 │
└─────────────────────────────────────┘

Mobile:
┌─────────────────────┐
│  Top Bar            │
│  (Hamburger + Logo) │
├─────────────────────┤
│  Main Content       │
│                     │
└─────────────────────┘
```

#### Content Editor Layout
```
Desktop (Split View):
┌─────────────────────────────────────┐
│  Editor (50%)     │  Preview (50%)  │
│                   │                 │
│  - AI Inputs      │  - Live Preview │
│  - Settings       │  - Platform View│
│  - Actions        │                 │
└─────────────────────────────────────┘

Mobile (Tabs):
Editor tab / Preview tab switching
```

---

## 🔄 User Flows & Wireframes

### Flow 1: Onboarding (7 Steps)

**Step 1: Welcome Screen**
```
Layout:
- Hero illustration (top)
- "Welcome to [Product]" (H1)
- "Let's get your marketing on autopilot" (subtitle)
- "Get Started" button (primary)
- "~5 minutes to setup" (small text)
```

**Step 2: Business Profile**
```
Form:
- "What industry are you in?" (dropdown)
- "Describe your business in a few words" (textarea)
- "Who is your target audience?" (tags input)
- Progress indicator: 2/7
- "Next" button
```

**Step 3: Connect Platforms**
```
Cards for each platform:
┌───────────────┐  ┌───────────────┐
│ [FB Logo]     │  │ [IG Logo]     │
│ Facebook      │  │ Instagram     │
│ Connect ────> │  │ Connect ────> │
└───────────────┘  └───────────────┘

- OAuth buttons
- "Skip for now" option
- At least 1 required to continue
```

**Step 4: Set Goals**
```
Large cards with icons:
□ Get more customers
□ Increase brand awareness
□ Drive website traffic
□ Build community
□ Launch new product

Select 1-2 primary goals
```

**Step 5: AI Strategy Generation**
```
Loading state:
- "Analyzing your business..."
- "Researching your industry..."
- "Creating your strategy..."

Then show:
┌─────────────────────────────────┐
│ 🧠 Your Custom Marketing Strategy│
│                                 │
│ Platform Mix:                   │
│ ▓▓▓▓▓▓ Instagram 60%           │
│ ▓▓▓ Facebook 30%               │
│ ▓ LinkedIn 10%                 │
│                                 │
│ Why? [Explanation]              │
│                                 │
│ [Looks Good] [Adjust Strategy]  │
└─────────────────────────────────┘
```

**Step 6: Content Preview**
```
Show 3-4 sample generated posts
- Visual preview for each platform
- "This is what your content will look like"
- Edit capabilities shown
```

**Step 7: Completion**
```
Success state:
- ✓ Checkmark animation
- "You're all set!"
- Show next steps:
  • Review your content calendar
  • Publish your first post
  • Invite team members
- "Go to Dashboard" button
```

### Flow 2: Content Generation & Publishing

**Step 1: Content Calendar View**
```
Layout:
┌─────────────────────────────────────┐
│ [Week View] [Month View]            │
├─────────────────────────────────────┤
│  Mon     Tue     Wed     Thu    Fri │
│ ┌───┐   ┌───┐   ┌───┐   ┌───┐ ┌───┐│
│ │📱 │   │📱 │   │   │   │📱 │ │📱 ││
│ │📘 │   │   │   │   │   │📘 │ │   ││
│ └───┘   └───┘   └───┘   └───┘ └───┘│
└─────────────────────────────────────┘

- [+ Generate More Content] button
- Filter by platform
- Drag to reschedule
```

**Step 2: Content Generation Modal**
```
┌─────────────────────────────────────┐
│ Generate Content                 [X]│
├─────────────────────────────────────┤
│                                     │
│ What would you like to post about?  │
│ ┌─────────────────────────────────┐│
│ │ [AI suggestion chips appear]    ││
│ │ "New product launch"            ││
│ │ "Customer testimonial"          ││
│ │ "Behind the scenes"             ││
│ │                                 ││
│ │ Or type your own idea...        ││
│ └─────────────────────────────────┘│
│                                     │
│ Platforms:                          │
│ [✓] Instagram  [ ] Facebook        │
│ [✓] LinkedIn   [ ] Twitter         │
│                                     │
│ Tone: [Professional ▼]             │
│                                     │
│           [Generate Content]        │
└─────────────────────────────────────┘
```

**Step 3: Review Generated Content**
```
Split view showing:

Left (Editor):
┌─────────────────────────┐
│ [Platform tabs]         │
│ Instagram               │
├─────────────────────────┤
│ Caption:                │
│ [Editable text]         │
│                         │
│ Image:                  │
│ [Thumbnail]             │
│ [Regenerate] [Upload]   │
│                         │
│ Hashtags:               │
│ #marketing #business    │
│ [Add more]              │
│                         │
│ [< Previous] [Next >]   │
└─────────────────────────┘

Right (Preview):
┌─────────────────────────┐
│ ┌─────────────────────┐ │
│ │ [Instagram UI       │ │
│ │  mockup showing     │ │
│ │  how post will      │ │
│ │  appear]            │ │
│ └─────────────────────┘ │
│                         │
│ Preview on:             │
│ [Instagram] [Facebook]  │
└─────────────────────────┘

Bottom actions:
[Save Draft] [Schedule] [Publish Now]
```

### Flow 3: Dashboard Overview

```
Layout (Desktop):
┌─────────────────────────────────────┐
│ Overview - Last 30 Days             │
├─────────────────────────────────────┤
│ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐   │
│ │ 12K │ │ 8.5%│ │ 450 │ │ 245 │   │
│ │Reach│ │ CTR │ │Likes│ │ New │   │
│ │+15% │ │+2.1%│ │-5%  │ │+32% │   │
│ └─────┘ └─────┘ └─────┘ └─────┘   │
├─────────────────────────────────────┤
│ Engagement Over Time                │
│ [Line graph]                        │
├─────────────────────────────────────┤
│ Top Performing Posts      [View All]│
│ ┌────────────────────────────────┐ │
│ │ [Thumbnail] Post title...       ││
│ │ 1.2K likes • 89 comments       ││
│ └────────────────────────────────┘ │
│ ┌────────────────────────────────┐ │
│ │ [Thumbnail] Post title...       ││
│ │ 980 likes • 56 comments        ││
│ └────────────────────────────────┘ │
├─────────────────────────────────────┤
│ AI Recommendations                  │
│ ┌────────────────────────────────┐ │
│ │ 💡 Your Tuesday posts get 2x   ││
│ │    more engagement. Schedule   ││
│ │    important content then.     ││
│ │    [Apply This Insight]        ││
│ └────────────────────────────────┘ │
└─────────────────────────────────────┘
```

---

## 🎭 Interaction Patterns

### Micro-interactions

**Button Clicks**
- Scale: 0.98 on active (slight press effect)
- Duration: 150ms
- Ease: ease-out

**Card Hovers**
- Transform: translateY(-2px)
- Shadow: sm → md transition
- Duration: 200ms
- Ease: ease-in-out

**Loading Dots**
- Three dots animate in sequence
- Opacity: 0.3 → 1.0 → 0.3
- Timing: 600ms per cycle

**Success Animations**
- Checkmark draws in (stroke animation)
- Color: Green 600
- Duration: 400ms
- Followed by subtle scale pulse

**AI Thinking Indicator**
- Gradient shimmer effect
- Colors: Primary 200 → Primary 400
- Duration: 1.5s loop
- Text: "AI is thinking..."

### Transitions

**Page Transitions**
- Fade + slight slide up
- Duration: 300ms
- Ease: ease-in-out

**Modal Open/Close**
- Scale from 0.9 to 1.0 + fade in
- Overlay fades in
- Duration: 250ms
- Ease: ease-out

**Drawer Slide (Mobile)**
- Slide from left/right
- Duration: 300ms
- Ease: ease-in-out
- Overlay fades in simultaneously

---

## 📐 Design Specifications

### Icons

**Icon Set:** Lucide Icons (or Heroicons)
**Default Size:** 20x20px
**Stroke Width:** 2px
**Colors:** Inherit from parent or Gray 600

Common Icons:
- Home: Home icon
- Content: File text icon
- Calendar: Calendar icon
- Analytics: Bar chart icon
- Settings: Settings icon
- AI: Sparkles or Brain icon
- Platform: Specific brand icons

### Illustrations

**Style:** 
- Flat, modern, minimal
- Use brand colors (Primary palette)
- No excessive detail
- Friendly but professional

**Usage:**
- Empty states
- Onboarding steps
- Error pages
- Feature highlights

**Sources:**
- Undraw.co (customized to brand colors)
- Custom illustrations for key moments

### Images

**Content Previews:**
- Aspect ratio: 1:1 (Instagram), 16:9 (YouTube), varies
- Max size: 1200px width
- Compression: WebP format
- Lazy loading below fold

**User Avatars:**
- Size: 32px (small), 40px (default), 64px (large)
- Shape: Circle
- Fallback: Initials on colored background

---

## 📱 Mobile Considerations

### Mobile-First Adaptations

**Navigation:**
- Sidebar → Bottom tab bar (5 items max)
- Or hamburger drawer
- Swipe gestures for navigation

**Cards:**
- Full width with 16px margin
- Stack vertically
- Reduce padding to 16px

**Forms:**
- Full width inputs
- Larger touch targets (44px minimum)
- Native date/time pickers
- Auto-focus on modal open

**Modals:**
- Full screen or slide up from bottom
- Easy to dismiss (swipe down)
- Large close button

**Tables:**
- Horizontal scroll
- Or card layout on mobile
- Show most important columns only

---

## ♿ Accessibility Guidelines

### Standards
- WCAG 2.1 AA compliance minimum
- AAA for text contrast where possible

### Color Contrast
- Body text: 4.5:1 minimum
- Large text (18px+): 3:1 minimum
- UI components: 3:1 minimum

### Keyboard Navigation
- All interactive elements focusable
- Visible focus indicators (2px outline)
- Logical tab order
- Escape closes modals
- Arrow keys for lists/dropdowns

### Screen Readers
- Semantic HTML (nav, main, section, etc.)
- ARIA labels for icon buttons
- Alt text for images
- Live regions for dynamic content
- Skip to main content link

### Motion
- Respect prefers-reduced-motion
- Provide static alternatives
- No auto-playing videos
- Pause/stop controls for animations

---

## 🎨 Brand Voice in UI

### Tone
**Confident but not arrogant**
- "We've got this" not "Trust us, we're experts"

**Helpful but not patronizing**
- "Here's what we recommend" not "You should do this"

**Clear but not robotic**
- "Your post is ready" not "Post creation successful"

### Microcopy Examples

**Empty States:**
❌ "No data available"
✅ "Let's create your first post!"

**Errors:**
❌ "Error 404: Resource not found"
✅ "Hmm, we couldn't find that page. Let's get you back on track."

**Success Messages:**
❌ "Operation completed successfully"
✅ "Great! Your post is scheduled for Tuesday at 3 PM"

**CTAs:**
❌ "Submit"
✅ "Generate My Strategy"

❌ "Click here"
✅ "Connect Instagram"

---

## 🔍 Design Quality Checklist

Before shipping any screen:

**Visual:**
- [ ] Follows color palette
- [ ] Uses correct typography scale
- [ ] Spacing is consistent (4px system)
- [ ] Proper contrast ratios
- [ ] Icons are correct size and weight

**Interaction:**
- [ ] Hover states defined
- [ ] Loading states shown
- [ ] Error states handled
- [ ] Empty states designed
- [ ] Success feedback provided

**Responsive:**
- [ ] Works at mobile (375px)
- [ ] Works at tablet (768px)
- [ ] Works at desktop (1440px)
- [ ] No horizontal scroll
- [ ] Touch targets 44px minimum

**Accessibility:**
- [ ] Keyboard navigable
- [ ] Focus indicators visible
- [ ] Alt text for images
- [ ] ARIA labels where needed
- [ ] Color not sole indicator

**Copy:**
- [ ] Clear and concise
- [ ] Matches brand voice
- [ ] No jargon
- [ ] Helpful error messages
- [ ] Action-oriented CTAs

---

## 🎯 Key Screens Priority

### Phase 1 (MVP)
1. Onboarding flow (7 screens)
2. Dashboard overview
3. Content calendar
4. Content generation modal
5. Content editor/preview
6. Platform connection
7. Settings/profile

### Phase 2
1. Analytics deep dive
2. Campaign management
3. Team collaboration
4. Billing/subscription
5. Template library

### Phase 3
1. Advanced strategy builder
2. Competitor analysis view
3. Revenue attribution
4. White-label admin

---

## 📚 Design Resources

### Tools
- **Design:** Figma
- **Prototyping:** Figma
- **Icon:** Lucide Icons
- **Illustrations:** Undraw, custom
- **Colors:** Tailwind CSS palette
- **Fonts:** Google Fonts (Inter, Plus Jakarta Sans)

### File Structure
```
/design-files/
├── design-system.fig (components library)
├── user-flows.fig (all flows)
├── mockups-mvp.fig (Phase 1 screens)
├── mockups-phase2.fig
├── prototypes.fig
└── assets/
    ├── icons/
    ├── illustrations/
    └── brand/
```

---

## 🔄 Design Review Process

**Weekly Design Review:**
1. Present new designs
2. Gather feedback from team
3. User test when possible
4. Iterate based on findings
5. Hand off to engineering

**Design Handoff Includes:**
- Figma link with dev mode enabled
- Component documentation
- Interaction specifications
- Asset exports
- Edge case notes

---

**Design Status:** Evolving  
**Next Review:** Weekly  
**Feedback:** [Design feedback channel]
