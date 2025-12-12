'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { usersApi } from '@/lib/api';
import toast from 'react-hot-toast';
import AddUserDialog from '@/components/users/AddUserDialog';
import EditUserDialog from '@/components/users/EditUserDialog';
import DeleteUserDialog from '@/components/users/DeleteUserDialog';
import BulkUploadDialog from '@/components/users/BulkUploadDialog';
import {
  Plus,
  Search,
  Filter,
  Users,
  User,
  Shield,
  Key,
  Building2,
  Activity,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Settings,
  Eye,
  Mail,
  Calendar,
  Clock,
  MoreVertical,
  UserCog,
  ShieldCheck,
  Lock,
  Edit,
  Trash2,
  Upload,
} from 'lucide-react';

interface UserType {
  id: number;
  email: string;
  full_name: string;
  user_type: 'gt_admin' | 'tenant_admin' | 'tenant_user';
  tenant_id?: number;
  tenant_name?: string;
  status: 'active' | 'inactive' | 'suspended';
  capabilities: string[];
  access_groups: string[];
  last_login?: string;
  created_at: string;
  api_calls_today?: number;
  active_sessions?: number;
}

export default function UsersPage() {
  const [users, setUsers] = useState<UserType[]>([]);
  const [filteredUsers, setFilteredUsers] = useState<UserType[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [selectedUsers, setSelectedUsers] = useState<Set<number>>(new Set());

  // Dialog states
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [bulkUploadDialogOpen, setBulkUploadDialogOpen] = useState(false);
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [userToDelete, setUserToDelete] = useState<{
    id: number;
    email: string;
    full_name: string;
    user_type: string;
  } | null>(null);

  // Fetch real users from API - GT 2.0 "No Mocks" principle
  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    try {
      setLoading(true);
      const response = await usersApi.list(1, 100);
      const userData = response.data?.users || response.data?.data || [];
      
      // Map API response to expected format
      const mappedUsers: UserType[] = userData.map((user: any) => ({
        ...user,
        status: user.is_active ? 'active' : 'suspended',
        api_calls_today: 0, // Will be populated by analytics API
        active_sessions: 0,  // Will be populated by sessions API
        capabilities: user.capabilities || [],
        access_groups: user.access_groups || [],
      }));
      
      setUsers(mappedUsers);
      setFilteredUsers(mappedUsers);
    } catch (error) {
      console.error('Failed to fetch users:', error);
      toast.error('Failed to load users');
      setUsers([]);
      setFilteredUsers([]);
    } finally {
      setLoading(false);
    }
  };

  // Filter users based on type and search
  useEffect(() => {
    let filtered = users;

    // Filter by user type
    if (typeFilter !== 'all') {
      filtered = filtered.filter(u => u.user_type === typeFilter);
    }

    // Filter by search query
    if (searchQuery) {
      filtered = filtered.filter(u =>
        u.full_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        u.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
        u.tenant_name?.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }

    setFilteredUsers(filtered);
  }, [typeFilter, searchQuery, users]);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'active':
        return <Badge variant="default" className="bg-green-600"><CheckCircle className="h-3 w-3 mr-1" />Active</Badge>;
      case 'inactive':
        return <Badge variant="secondary"><Clock className="h-3 w-3 mr-1" />Inactive</Badge>;
      case 'suspended':
        return <Badge variant="destructive"><XCircle className="h-3 w-3 mr-1" />Suspended</Badge>;
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  const getUserTypeBadge = (type: string) => {
    switch (type) {
      case 'gt_admin':
        return <Badge className="bg-purple-600"><ShieldCheck className="h-3 w-3 mr-1" />GT Admin</Badge>;
      case 'tenant_admin':
        return <Badge className="bg-blue-600"><UserCog className="h-3 w-3 mr-1" />Tenant Admin</Badge>;
      case 'tenant_user':
        return <Badge variant="secondary"><User className="h-3 w-3 mr-1" />User</Badge>;
      default:
        return <Badge variant="secondary">{type}</Badge>;
    }
  };

  const typeTabs = [
    { id: 'all', label: 'All Users', count: users.length },
    { id: 'gt_admin', label: 'GT Admins', count: users.filter(u => u.user_type === 'gt_admin').length },
    { id: 'tenant_admin', label: 'Tenant Admins', count: users.filter(u => u.user_type === 'tenant_admin').length },
    { id: 'tenant_user', label: 'Tenant Users', count: users.filter(u => u.user_type === 'tenant_user').length },
  ];

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">User Management</h1>
          <p className="text-muted-foreground">
            Manage users, capabilities, and access groups across all tenants
          </p>
        </div>
        <div className="flex space-x-2">
          <Button variant="secondary">
            <Shield className="h-4 w-4 mr-2" />
            Access Groups
          </Button>
          <Button variant="secondary" onClick={() => setBulkUploadDialogOpen(true)}>
            <Upload className="h-4 w-4 mr-2" />
            Bulk Upload
          </Button>
          <Button onClick={() => setAddDialogOpen(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Add User
          </Button>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total Users</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{users.length}</div>
            <p className="text-xs text-muted-foreground">
              {users.filter(u => u.status === 'active').length} active
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Active Sessions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {users.reduce((sum, u) => sum + (u.active_sessions || 0), 0)}
            </div>
            <p className="text-xs text-muted-foreground">
              Currently online
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">API Usage</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {(users.reduce((sum, u) => sum + (u.api_calls_today || 0), 0) / 1000).toFixed(1)}K
            </div>
            <p className="text-xs text-muted-foreground">
              Calls today
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Access Groups</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {Array.from(new Set(users.flatMap(u => u.access_groups))).length}
            </div>
            <p className="text-xs text-muted-foreground">
              Unique groups
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Type Tabs */}
      <div className="flex space-x-2 border-b">
        {typeTabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setTypeFilter(tab.id)}
            className={`px-4 py-2 border-b-2 transition-colors ${
              typeFilter === tab.id
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            <span>{tab.label}</span>
            <Badge variant="secondary" className="ml-2">{tab.count}</Badge>
          </button>
        ))}
      </div>

      {/* Search and Filters */}
      <div className="flex space-x-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search users by name, email, or tenant..."
            value={searchQuery}
            onChange={(e) => setSearchQuery((e as React.ChangeEvent<HTMLInputElement>).target.value)}
            className="pl-10"
          />
        </div>
        <Button variant="secondary">
          <Filter className="h-4 w-4 mr-2" />
          Filters
        </Button>
      </div>

      {/* Bulk Actions */}
      {selectedUsers.size > 0 && (
        <Card className="bg-muted/50">
          <CardContent className="flex items-center justify-between py-3">
            <span className="text-sm">
              {selectedUsers.size} user{selectedUsers.size > 1 ? 's' : ''} selected
            </span>
            <div className="flex space-x-2">
              <Button variant="secondary" size="sm">
                <Key className="h-4 w-4 mr-2" />
                Reset Passwords
              </Button>
              <Button variant="secondary" size="sm" className="text-destructive">
                <Lock className="h-4 w-4 mr-2" />
                Suspend
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Users Table */}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <Activity className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="border-b bg-muted/50">
                  <tr>
                    <th className="p-4 text-left">
                      <input
                        type="checkbox"
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedUsers(new Set(filteredUsers.map(u => u.id)));
                          } else {
                            setSelectedUsers(new Set());
                          }
                        }}
                        checked={selectedUsers.size === filteredUsers.length && filteredUsers.length > 0}
                      />
                    </th>
                    <th className="p-4 text-left font-medium">User</th>
                    <th className="p-4 text-left font-medium">Type</th>
                    <th className="p-4 text-left font-medium">Tenant</th>
                    <th className="p-4 text-left font-medium">Status</th>
                    <th className="p-4 text-left font-medium">Activity</th>
                    <th className="p-4 text-left font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredUsers.map(user => (
                    <tr key={user.id} className="border-b hover:bg-muted/30">
                      <td className="p-4">
                        <input
                          type="checkbox"
                          checked={selectedUsers.has(user.id)}
                          onChange={(e) => {
                            const newSelected = new Set(selectedUsers);
                            if (e.target.checked) {
                              newSelected.add(user.id);
                            } else {
                              newSelected.delete(user.id);
                            }
                            setSelectedUsers(newSelected);
                          }}
                        />
                      </td>
                      <td className="p-4">
                        <div>
                          <div className="font-medium">{user.full_name}</div>
                          <div className="text-sm text-muted-foreground flex items-center space-x-1">
                            <Mail className="h-3 w-3" />
                            <span>{user.email}</span>
                          </div>
                        </div>
                      </td>
                      <td className="p-4">
                        {getUserTypeBadge(user.user_type)}
                      </td>
                      <td className="p-4">
                        {user.tenant_name ? (
                          <div className="flex items-center space-x-1">
                            <Building2 className="h-4 w-4 text-muted-foreground" />
                            <span>{user.tenant_name}</span>
                          </div>
                        ) : (
                          <span className="text-muted-foreground">System</span>
                        )}
                      </td>
                      <td className="p-4">
                        {getStatusBadge(user.status)}
                      </td>
                      <td className="p-4">
                        <div className="space-y-1 text-sm">
                          {user.last_login && (
                            <div className="flex items-center space-x-1">
                              <Clock className="h-3 w-3 text-muted-foreground" />
                              <span>{new Date(user.last_login).toLocaleTimeString()}</span>
                            </div>
                          )}
                          {user.api_calls_today !== undefined && (
                            <div className="flex items-center space-x-1">
                              <Activity className="h-3 w-3 text-muted-foreground" />
                              <span>{user.api_calls_today} calls</span>
                            </div>
                          )}
                          {user.active_sessions !== undefined && user.active_sessions > 0 && (
                            <Badge variant="secondary" className="text-xs">
                              {user.active_sessions} session{user.active_sessions > 1 ? 's' : ''}
                            </Badge>
                          )}
                        </div>
                      </td>
                      <td className="p-4">
                        <div className="flex space-x-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              setSelectedUserId(user.id);
                              setEditDialogOpen(true);
                            }}
                          >
                            <Edit className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              setUserToDelete({
                                id: user.id,
                                email: user.email,
                                full_name: user.full_name,
                                user_type: user.user_type,
                              });
                              setDeleteDialogOpen(true);
                            }}
                          >
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Dialogs */}
      <AddUserDialog
        open={addDialogOpen}
        onOpenChange={setAddDialogOpen}
        onUserAdded={fetchUsers}
      />

      <EditUserDialog
        open={editDialogOpen}
        onOpenChange={setEditDialogOpen}
        userId={selectedUserId}
        onUserUpdated={fetchUsers}
      />

      <DeleteUserDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        user={userToDelete}
        onUserDeleted={fetchUsers}
      />

      <BulkUploadDialog
        open={bulkUploadDialogOpen}
        onOpenChange={setBulkUploadDialogOpen}
        onUploadComplete={fetchUsers}
      />
    </div>
  );
}