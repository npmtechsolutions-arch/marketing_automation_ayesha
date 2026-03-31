# RBAC & Permissions System
## Role-Based Access Control Documentation

---

## 📋 Document Information

- **Product:** AI Marketing Automation Platform
- **Document Type:** RBAC & Permissions Specification
- **Last Updated:** 2025-02-16
- **Status:** Implementation Ready

---

## 🎯 RBAC Overview

### What is RBAC?
Role-Based Access Control (RBAC) is a security model that restricts system access based on user roles. Each role has specific permissions defining what actions they can perform.

### Why RBAC?
- ✅ Security: Users only access what they need
- ✅ Scalability: Easy to manage permissions for many users
- ✅ Compliance: Audit trails and access control
- ✅ Flexibility: Easy to add new roles

---

## 👥 User Roles

### Role Hierarchy

```
Super Admin (System Level)
    ↓
Owner (Account Level)
    ↓
Admin (Account Level)
    ↓
Manager (Account Level)
    ↓
Editor (Account Level)
    ↓
Viewer (Account Level)
```

---

## 🔐 Role Definitions

### 1. Super Admin
**Who:** Platform administrators (your team)
**Scope:** Entire platform
**Use Case:** Platform maintenance, support, monitoring

**Permissions:**
- ✅ View all accounts
- ✅ Impersonate users (for support)
- ✅ Modify any data
- ✅ Access admin panel
- ✅ View system logs
- ✅ Manage subscriptions manually
- ✅ Override rate limits
- ✅ Access database directly
- ❌ Cannot delete accounts (safety)

**Database:**
```sql
CREATE TABLE super_admins (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    granted_at TIMESTAMP DEFAULT NOW(),
    granted_by UUID REFERENCES super_admins(user_id),
    is_active BOOLEAN DEFAULT true
);
```

---

### 2. Owner
**Who:** Account creator, business owner
**Scope:** Their account only
**Use Case:** Full control of their business account

**Permissions:**
- ✅ Full access to all features
- ✅ Manage subscription & billing
- ✅ Add/remove team members
- ✅ Assign roles to team members
- ✅ Delete account
- ✅ Export all data
- ✅ Connect/disconnect platforms
- ✅ Generate, edit, delete content
- ✅ Publish posts
- ✅ View analytics
- ✅ Configure AI strategy
- ✅ View audit logs
- ✅ Transfer ownership

**Special Notes:**
- Only ONE owner per account
- Cannot be removed (only transferred)
- Automatically assigned on signup

**Database:**
```sql
-- Owner is marked in users table
ALTER TABLE users ADD COLUMN role VARCHAR(50) DEFAULT 'owner';
ALTER TABLE users ADD COLUMN account_id UUID REFERENCES accounts(id);
```

---

### 3. Admin
**Who:** Trusted team members
**Scope:** Their account
**Use Case:** Manage operations, oversee team

**Permissions:**
- ✅ Add/remove Editors, Viewers (not other Admins)
- ✅ Connect/disconnect platforms
- ✅ Generate, edit, delete content
- ✅ Publish posts
- ✅ View analytics
- ✅ Configure AI strategy
- ✅ View audit logs
- ✅ Manage content calendar
- ✅ Approve/reject content
- ❌ Cannot manage billing
- ❌ Cannot delete account
- ❌ Cannot add/remove Admins
- ❌ Cannot transfer ownership

**Database:**
```sql
CREATE TABLE team_members (
    id UUID PRIMARY KEY,
    account_id UUID REFERENCES accounts(id),
    user_id UUID REFERENCES users(id),
    role VARCHAR(50), -- 'admin', 'manager', 'editor', 'viewer'
    invited_by UUID REFERENCES users(id),
    invited_at TIMESTAMP DEFAULT NOW(),
    accepted_at TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    UNIQUE(account_id, user_id)
);
```

---

### 4. Manager
**Who:** Marketing managers, team leads
**Scope:** Their account
**Use Case:** Oversee content creation, approve posts

**Permissions:**
- ✅ Generate, edit content
- ✅ Publish posts (with approval workflow if enabled)
- ✅ View analytics
- ✅ Manage content calendar
- ✅ Approve/reject content (if approval workflow enabled)
- ✅ Comment on content
- ❌ Cannot connect/disconnect platforms
- ❌ Cannot configure AI strategy
- ❌ Cannot add/remove team members
- ❌ Cannot view audit logs
- ❌ Cannot manage billing

---

### 5. Editor
**Who:** Content creators, social media managers
**Scope:** Their account
**Use Case:** Create and edit content

**Permissions:**
- ✅ Generate content
- ✅ Edit content (own and drafts)
- ✅ Schedule posts
- ✅ Submit for approval (if approval workflow enabled)
- ✅ View basic analytics
- ✅ Comment on content
- ❌ Cannot publish directly (if approval workflow enabled)
- ❌ Cannot delete published posts
- ❌ Cannot connect/disconnect platforms
- ❌ Cannot configure AI strategy
- ❌ Cannot manage team members

---

### 6. Viewer
**Who:** Clients, stakeholders, junior team members
**Scope:** Their account
**Use Case:** View-only access for reporting

**Permissions:**
- ✅ View published content
- ✅ View analytics
- ✅ View content calendar (read-only)
- ✅ Export reports
- ✅ Comment on content
- ❌ Cannot create content
- ❌ Cannot edit content
- ❌ Cannot publish posts
- ❌ Cannot connect platforms
- ❌ Cannot manage team members
- ❌ Cannot access settings

---

## 📊 Permissions Matrix

### Complete Permissions Table

| Permission | Super Admin | Owner | Admin | Manager | Editor | Viewer |
|------------|-------------|-------|-------|---------|--------|--------|
| **Account Management** |
| View account details | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Edit account settings | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Delete account | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Transfer ownership | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Billing** |
| View billing | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Update payment method | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Change subscription | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| View invoices | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Team Management** |
| Invite users | ✅ | ✅ | ✅* | ❌ | ❌ | ❌ |
| Remove users | ✅ | ✅ | ✅* | ❌ | ❌ | ❌ |
| Change user roles | ✅ | ✅ | ✅* | ❌ | ❌ | ❌ |
| View team members | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| **Platform Connections** |
| Connect platforms | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Disconnect platforms | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| View connected platforms | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Refresh tokens | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| **Content Creation** |
| Generate content | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| Edit own content | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| Edit others' content | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| Delete drafts | ✅ | ✅ | ✅ | ✅ | ✅** | ❌ |
| Delete published | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| **Publishing** |
| Publish immediately | ✅ | ✅ | ✅ | ✅ | ✅*** | ❌ |
| Schedule posts | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| Cancel scheduled | ✅ | ✅ | ✅ | ✅ | ✅** | ❌ |
| Approve content | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| Reject content | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| **Analytics** |
| View analytics | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Export reports | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| View performance | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **AI Strategy** |
| View strategy | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Edit strategy | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Apply AI recommendations | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| **Settings** |
| View settings | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| Edit settings | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| View audit logs | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| **System** |
| Impersonate users | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Access admin panel | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| View system logs | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

**Notes:**
- \* Admin can only manage Editor and Viewer roles (not other Admins)
- \*\* Editor can only delete/cancel their own content
- \*\*\* Editor requires approval if approval workflow is enabled

---

## 🔧 Implementation

### Database Schema

```sql
-- Accounts table
CREATE TABLE accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    owner_id UUID REFERENCES users(id),
    subscription_tier VARCHAR(50) DEFAULT 'free',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Users table (updated)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255),
    full_name VARCHAR(255),
    is_super_admin BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Team members (roles assigned here)
CREATE TABLE team_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID REFERENCES accounts(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL CHECK (role IN ('owner', 'admin', 'manager', 'editor', 'viewer')),
    invited_by UUID REFERENCES users(id),
    invited_at TIMESTAMP DEFAULT NOW(),
    accepted_at TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    UNIQUE(account_id, user_id)
);

CREATE INDEX idx_team_members_account ON team_members(account_id);
CREATE INDEX idx_team_members_user ON team_members(user_id);
CREATE INDEX idx_team_members_role ON team_members(role);

-- Permissions (granular control)
CREATE TABLE permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) UNIQUE NOT NULL,
    resource VARCHAR(100) NOT NULL, -- 'content', 'analytics', 'settings', etc.
    action VARCHAR(50) NOT NULL, -- 'create', 'read', 'update', 'delete', 'publish'
    description TEXT
);

-- Role permissions mapping
CREATE TABLE role_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role VARCHAR(50) NOT NULL,
    permission_id UUID REFERENCES permissions(id),
    UNIQUE(role, permission_id)
);

-- Custom permissions (override for specific users)
CREATE TABLE user_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_member_id UUID REFERENCES team_members(id) ON DELETE CASCADE,
    permission_id UUID REFERENCES permissions(id),
    is_granted BOOLEAN DEFAULT true, -- true = grant, false = revoke
    granted_by UUID REFERENCES users(id),
    granted_at TIMESTAMP DEFAULT NOW()
);
```

### Seed Permissions

```sql
-- Insert all permissions
INSERT INTO permissions (name, resource, action, description) VALUES
-- Account permissions
('account.view', 'account', 'read', 'View account details'),
('account.edit', 'account', 'update', 'Edit account settings'),
('account.delete', 'account', 'delete', 'Delete account'),
('account.transfer', 'account', 'transfer', 'Transfer account ownership'),

-- Billing permissions
('billing.view', 'billing', 'read', 'View billing information'),
('billing.edit', 'billing', 'update', 'Update payment methods'),
('billing.manage', 'billing', 'manage', 'Manage subscriptions'),

-- Team permissions
('team.view', 'team', 'read', 'View team members'),
('team.invite', 'team', 'create', 'Invite team members'),
('team.remove', 'team', 'delete', 'Remove team members'),
('team.edit_roles', 'team', 'update', 'Change team member roles'),

-- Platform permissions
('platform.view', 'platform', 'read', 'View connected platforms'),
('platform.connect', 'platform', 'create', 'Connect new platforms'),
('platform.disconnect', 'platform', 'delete', 'Disconnect platforms'),

-- Content permissions
('content.view', 'content', 'read', 'View content'),
('content.create', 'content', 'create', 'Create content'),
('content.edit_own', 'content', 'update', 'Edit own content'),
('content.edit_any', 'content', 'update', 'Edit any content'),
('content.delete_own', 'content', 'delete', 'Delete own content'),
('content.delete_any', 'content', 'delete', 'Delete any content'),

-- Publishing permissions
('content.publish', 'content', 'publish', 'Publish content immediately'),
('content.schedule', 'content', 'schedule', 'Schedule content'),
('content.approve', 'content', 'approve', 'Approve content for publishing'),
('content.reject', 'content', 'reject', 'Reject content'),

-- Analytics permissions
('analytics.view', 'analytics', 'read', 'View analytics'),
('analytics.export', 'analytics', 'export', 'Export reports'),

-- Strategy permissions
('strategy.view', 'strategy', 'read', 'View AI strategy'),
('strategy.edit', 'strategy', 'update', 'Edit AI strategy'),

-- Settings permissions
('settings.view', 'settings', 'read', 'View settings'),
('settings.edit', 'settings', 'update', 'Edit settings'),
('settings.audit', 'settings', 'read', 'View audit logs');
```

### Map Roles to Permissions

```sql
-- Owner permissions (all permissions)
INSERT INTO role_permissions (role, permission_id)
SELECT 'owner', id FROM permissions;

-- Admin permissions (all except billing and account deletion)
INSERT INTO role_permissions (role, permission_id)
SELECT 'admin', id FROM permissions
WHERE name NOT IN ('billing.view', 'billing.edit', 'billing.manage', 'account.delete', 'account.transfer');

-- Manager permissions
INSERT INTO role_permissions (role, permission_id)
SELECT 'manager', id FROM permissions
WHERE name IN (
    'account.view',
    'team.view',
    'platform.view',
    'content.view', 'content.create', 'content.edit_own', 'content.edit_any', 'content.delete_own',
    'content.publish', 'content.schedule', 'content.approve', 'content.reject',
    'analytics.view', 'analytics.export',
    'strategy.view',
    'settings.view'
);

-- Editor permissions
INSERT INTO role_permissions (role, permission_id)
SELECT 'editor', id FROM permissions
WHERE name IN (
    'account.view',
    'team.view',
    'platform.view',
    'content.view', 'content.create', 'content.edit_own', 'content.delete_own',
    'content.publish', 'content.schedule',
    'analytics.view',
    'strategy.view'
);

-- Viewer permissions
INSERT INTO role_permissions (role, permission_id)
SELECT 'viewer', id FROM permissions
WHERE name IN (
    'account.view',
    'content.view',
    'analytics.view', 'analytics.export',
    'strategy.view'
);
```

---

## 💻 Backend Implementation

### Permission Check Utility

```python
# app/utils/permissions.py
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models import User, TeamMember, Permission, RolePermission, UserPermission

def has_permission(
    db: Session,
    user_id: str,
    account_id: str,
    permission_name: str
) -> bool:
    """
    Check if user has specific permission in account.
    
    Priority:
    1. Super admin - always has access
    2. Custom user permissions (overrides)
    3. Role-based permissions
    """
    
    # Check if super admin
    user = db.query(User).filter(User.id == user_id).first()
    if user and user.is_super_admin:
        return True
    
    # Get team member
    team_member = db.query(TeamMember).filter(
        TeamMember.user_id == user_id,
        TeamMember.account_id == account_id,
        TeamMember.is_active == True
    ).first()
    
    if not team_member:
        return False
    
    # Check custom permissions (overrides)
    permission = db.query(Permission).filter(
        Permission.name == permission_name
    ).first()
    
    if permission:
        custom_perm = db.query(UserPermission).filter(
            UserPermission.team_member_id == team_member.id,
            UserPermission.permission_id == permission.id
        ).first()
        
        if custom_perm:
            return custom_perm.is_granted
    
    # Check role permissions
    role_perm = db.query(RolePermission).join(Permission).filter(
        RolePermission.role == team_member.role,
        Permission.name == permission_name
    ).first()
    
    return role_perm is not None


def has_any_permission(
    db: Session,
    user_id: str,
    account_id: str,
    permission_names: List[str]
) -> bool:
    """Check if user has ANY of the listed permissions."""
    return any(
        has_permission(db, user_id, account_id, perm)
        for perm in permission_names
    )


def has_all_permissions(
    db: Session,
    user_id: str,
    account_id: str,
    permission_names: List[str]
) -> bool:
    """Check if user has ALL of the listed permissions."""
    return all(
        has_permission(db, user_id, account_id, perm)
        for perm in permission_names
    )


def get_user_permissions(
    db: Session,
    user_id: str,
    account_id: str
) -> List[str]:
    """Get list of all permissions user has in account."""
    
    user = db.query(User).filter(User.id == user_id).first()
    if user and user.is_super_admin:
        # Super admin has all permissions
        return [p.name for p in db.query(Permission).all()]
    
    team_member = db.query(TeamMember).filter(
        TeamMember.user_id == user_id,
        TeamMember.account_id == account_id,
        TeamMember.is_active == True
    ).first()
    
    if not team_member:
        return []
    
    # Get role permissions
    role_perms = db.query(Permission).join(RolePermission).filter(
        RolePermission.role == team_member.role
    ).all()
    
    perm_names = {p.name for p in role_perms}
    
    # Apply custom permissions (overrides)
    custom_perms = db.query(UserPermission, Permission).join(Permission).filter(
        UserPermission.team_member_id == team_member.id
    ).all()
    
    for user_perm, perm in custom_perms:
        if user_perm.is_granted:
            perm_names.add(perm.name)
        else:
            perm_names.discard(perm.name)
    
    return list(perm_names)
```

### FastAPI Dependencies

```python
# app/dependencies.py
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.utils.auth import get_current_user
from app.utils.permissions import has_permission

def require_permission(permission_name: str):
    """Dependency to require specific permission."""
    
    async def permission_checker(
        account_id: str,
        current_user = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        if not has_permission(db, current_user.id, account_id, permission_name):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission_name} required"
            )
        return current_user
    
    return permission_checker


def require_any_permission(*permission_names: str):
    """Require ANY of the listed permissions."""
    
    async def permission_checker(
        account_id: str,
        current_user = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        if not has_any_permission(db, current_user.id, account_id, permission_names):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: one of {permission_names} required"
            )
        return current_user
    
    return permission_checker


def require_role(*roles: str):
    """Require specific role(s)."""
    
    async def role_checker(
        account_id: str,
        current_user = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        team_member = db.query(TeamMember).filter(
            TeamMember.user_id == current_user.id,
            TeamMember.account_id == account_id,
            TeamMember.is_active == True
        ).first()
        
        if not team_member or team_member.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role denied: {roles} required"
            )
        return current_user
    
    return role_checker
```

### API Endpoint Examples

```python
# app/api/v1/content.py
from fastapi import APIRouter, Depends
from app.dependencies import require_permission, require_role

router = APIRouter()

@router.post("/content")
async def create_content(
    account_id: str,
    content_data: ContentCreate,
    current_user = Depends(require_permission("content.create")),
    db: Session = Depends(get_db)
):
    """Create new content - requires content.create permission."""
    # Implementation
    pass


@router.put("/content/{content_id}")
async def update_content(
    account_id: str,
    content_id: str,
    content_data: ContentUpdate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update content - checks ownership or edit_any permission."""
    
    # Get content
    content = db.query(Content).filter(Content.id == content_id).first()
    
    # Check if owner or has edit_any permission
    can_edit = (
        content.created_by == current_user.id and 
        has_permission(db, current_user.id, account_id, "content.edit_own")
    ) or has_permission(db, current_user.id, account_id, "content.edit_any")
    
    if not can_edit:
        raise HTTPException(status_code=403, detail="Cannot edit this content")
    
    # Update content
    # ...


@router.post("/content/{content_id}/publish")
async def publish_content(
    account_id: str,
    content_id: str,
    current_user = Depends(require_permission("content.publish")),
    db: Session = Depends(get_db)
):
    """Publish content - requires content.publish permission."""
    # Implementation
    pass


@router.post("/team/invite")
async def invite_team_member(
    account_id: str,
    invite_data: TeamInvite,
    current_user = Depends(require_permission("team.invite")),
    db: Session = Depends(get_db)
):
    """Invite team member - requires team.invite permission."""
    
    # Check if inviting role is allowed
    inviter_member = db.query(TeamMember).filter(
        TeamMember.user_id == current_user.id,
        TeamMember.account_id == account_id
    ).first()
    
    # Admins can only invite Editor and Viewer
    if inviter_member.role == 'admin' and invite_data.role in ['owner', 'admin']:
        raise HTTPException(
            status_code=403,
            detail="Admins cannot invite Owner or Admin roles"
        )
    
    # Implementation
    pass
```

---

## 🎨 Frontend Implementation

### Permission Check Hook

```typescript
// hooks/usePermissions.ts
import { useAuth } from './useAuth';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/services/api';

export const usePermissions = (accountId: string) => {
  const { user } = useAuth();
  
  const { data: permissions, isLoading } = useQuery({
    queryKey: ['permissions', accountId, user?.id],
    queryFn: () => api.get(`/accounts/${accountId}/permissions`),
    enabled: !!accountId && !!user,
  });
  
  const hasPermission = (permission: string): boolean => {
    if (!permissions) return false;
    return permissions.includes(permission);
  };
  
  const hasAnyPermission = (...perms: string[]): boolean => {
    return perms.some(perm => hasPermission(perm));
  };
  
  const hasAllPermissions = (...perms: string[]): boolean => {
    return perms.every(perm => hasPermission(perm));
  };
  
  const hasRole = (...roles: string[]): boolean => {
    if (!permissions?.role) return false;
    return roles.includes(permissions.role);
  };
  
  return {
    permissions: permissions || [],
    role: permissions?.role,
    hasPermission,
    hasAnyPermission,
    hasAllPermissions,
    hasRole,
    isLoading,
  };
};
```

### Permission Components

```typescript
// components/auth/PermissionGate.tsx
import { usePermissions } from '@/hooks/usePermissions';

interface PermissionGateProps {
  permission?: string;
  permissions?: string[];
  requireAll?: boolean;
  role?: string | string[];
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export const PermissionGate: React.FC<PermissionGateProps> = ({
  permission,
  permissions,
  requireAll = false,
  role,
  children,
  fallback = null,
}) => {
  const { 
    hasPermission, 
    hasAnyPermission, 
    hasAllPermissions,
    hasRole 
  } = usePermissions();
  
  let hasAccess = false;
  
  if (role) {
    const roles = Array.isArray(role) ? role : [role];
    hasAccess = hasRole(...roles);
  } else if (permission) {
    hasAccess = hasPermission(permission);
  } else if (permissions) {
    hasAccess = requireAll 
      ? hasAllPermissions(...permissions)
      : hasAnyPermission(...permissions);
  }
  
  return hasAccess ? <>{children}</> : <>{fallback}</>;
};
```

### Usage Examples

```typescript
// Example 1: Hide button for users without permission
<PermissionGate permission="content.publish">
  <Button onClick={publishContent}>Publish Now</Button>
</PermissionGate>

// Example 2: Show different UI for different roles
<PermissionGate role={['owner', 'admin']} fallback={<ViewOnlyMode />}>
  <FullEditorMode />
</PermissionGate>

// Example 3: Require multiple permissions
<PermissionGate 
  permissions={['content.create', 'content.publish']} 
  requireAll={true}
>
  <QuickPublishButton />
</PermissionGate>

// Example 4: Conditional rendering in components
const ContentEditor = () => {
  const { hasPermission } = usePermissions();
  
  return (
    <div>
      <textarea value={content} onChange={handleChange} />
      
      {hasPermission('content.publish') && (
        <Button>Publish</Button>
      )}
      
      {hasPermission('content.schedule') && (
        <Button>Schedule</Button>
      )}
    </div>
  );
};
```

---

## 🔍 Audit Logging

Track all permission-sensitive actions:

```sql
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID REFERENCES accounts(id),
    user_id UUID REFERENCES users(id),
    action VARCHAR(100) NOT NULL, -- 'content.publish', 'team.invite', etc.
    resource_type VARCHAR(50), -- 'content', 'team_member', etc.
    resource_id UUID,
    details JSONB, -- Additional context
    ip_address VARCHAR(50),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_audit_account ON audit_logs(account_id);
CREATE INDEX idx_audit_user ON audit_logs(user_id);
CREATE INDEX idx_audit_created ON audit_logs(created_at);
```

---

## ✅ RBAC Implementation Checklist

### Database
- [ ] Create all RBAC tables
- [ ] Seed permissions
- [ ] Map roles to permissions
- [ ] Add indexes

### Backend
- [ ] Implement permission check utility
- [ ] Create FastAPI dependencies
- [ ] Add permission checks to all endpoints
- [ ] Implement audit logging
- [ ] Write permission tests

### Frontend
- [ ] Create usePermissions hook
- [ ] Build PermissionGate component
- [ ] Add role-based UI rendering
- [ ] Hide/disable features based on permissions
- [ ] Show appropriate error messages

### Testing
- [ ] Unit tests for permission logic
- [ ] Integration tests for API endpoints
- [ ] E2E tests for role-based flows
- [ ] Test all role combinations

### Documentation
- [ ] Document all permissions
- [ ] Create role comparison guide
- [ ] Write admin guide for managing team
- [ ] User documentation for roles

---

**RBAC Status:** Implementation Ready  
**Next Steps:** Implement database schema → Backend logic → Frontend components  
**Review:** Before production deployment
