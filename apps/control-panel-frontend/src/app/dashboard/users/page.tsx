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
  RotateCcw,
  ShieldOff,
} from 'lucide-react';

interface UserType {
  id: number;
  email: string;
  full_name: string;
  user_type: 'super_admin' | 'tenant_admin' | 'tenant_user';
  tenant_id?: number;
  tenant_name?: string;
  status: 'active' | 'inactive' | 'suspended';
  capabilities: string[];
  access_groups: string[];
  last_login?: string;
  created_at: string;
  tfa_enabled?: boolean;
  tfa_required?: boolean;
  tfa_status?: 'disabled' | 'enabled' | 'enforced';
}

export default function UsersPage() {
  const [users, setUsers] = useState<UserType[]>([]);
  const [filteredUsers, setFilteredUsers] = useState<UserType[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [selectedUsers, setSelectedUsers] = useState<Set<number>>(new Set());
  const [currentPage, setCurrentPage] = useState(1);
  const [totalUsers, setTotalUsers] = useState(0);
  const [limit] = useState(20);
  const [searchInput, setSearchInput] = useState('');
  const [roleCounts, setRoleCounts] = useState({
    super_admin: 0,
    tenant_admin: 0,
    tenant_user: 0,
  });

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

  // Fetch role counts on mount
  useEffect(() => {
    fetchRoleCounts();
  }, []);

  // Fetch real users from API - GT 2.0 "No Mocks" principle
  useEffect(() => {
    fetchUsers();
  }, [currentPage, searchQuery, typeFilter]);

  const fetchRoleCounts = async () => {
    try {
      // Fetch counts for each role
      const [superAdminRes, tenantAdminRes, tenantUserRes] = await Promise.all([
        usersApi.list(1, 1, undefined, undefined, 'super_admin'),
        usersApi.list(1, 1, undefined, undefined, 'tenant_admin'),
        usersApi.list(1, 1, undefined, undefined, 'tenant_user'),
      ]);

      setRoleCounts({
        super_admin: superAdminRes.data?.total || 0,
        tenant_admin: tenantAdminRes.data?.total || 0,
        tenant_user: tenantUserRes.data?.total || 0,
      });
    } catch (error) {
      console.error('Failed to fetch role counts:', error);
    }
  };

  const fetchUsers = async () => {
    try {
      setLoading(true);
      const response = await usersApi.list(
        currentPage,
        limit,
        searchQuery || undefined,
        undefined,
        typeFilter !== 'all' ? typeFilter : undefined
      );
      const userData = response.data?.users || response.data?.data || [];
      setTotalUsers(response.data?.total || 0);

      // Map API response to expected format
      const mappedUsers: UserType[] = userData.map((user: any) => ({
        ...user,
        status: user.is_active ? 'active' : 'suspended',
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

  const handleSearch = () => {
    setSearchQuery(searchInput);
    setCurrentPage(1); // Reset to first page on new search
  };

  const handleSearchKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  const handleTypeFilterChange = (newFilter: string) => {
    setTypeFilter(newFilter);
    setCurrentPage(1); // Reset to first page on filter change
  };

  const handleSelectAll = async () => {
    // Fetch all user IDs with current filters
    try {
      const response = await usersApi.list(
        1,
        totalUsers, // Get all users
        searchQuery || undefined,
        undefined,
        typeFilter !== 'all' ? typeFilter : undefined
      );
      const allUserIds = response.data?.users?.map((u: any) => u.id) || [];
      setSelectedUsers(new Set(allUserIds));
    } catch (error) {
      console.error('Failed to fetch all users:', error);
      toast.error('Failed to select all users');
    }
  };

  const handleDeleteSelected = async () => {
    if (selectedUsers.size === 0) return;

    const confirmMessage = `Are you sure you want to permanently delete ${selectedUsers.size} user${selectedUsers.size > 1 ? 's' : ''}? This action cannot be undone.`;

    if (!confirm(confirmMessage)) return;

    try {
      // Delete each selected user
      const deletePromises = Array.from(selectedUsers).map(userId =>
        usersApi.delete(userId)
      );

      await Promise.all(deletePromises);

      toast.success(`Successfully deleted ${selectedUsers.size} user${selectedUsers.size > 1 ? 's' : ''}`);
      setSelectedUsers(new Set());
      fetchUsers(); // Reload the user list
      fetchRoleCounts(); // Update role counts
    } catch (error) {
      console.error('Failed to delete users:', error);
      toast.error('Failed to delete some users');
      fetchUsers(); // Reload to show which users were actually deleted
    }
  };

  const handleResetTFA = async () => {
    if (selectedUsers.size === 0) return;

    const confirmMessage = `Reset 2FA for ${selectedUsers.size} user${selectedUsers.size > 1 ? 's' : ''}? They will need to set up 2FA again if required.`;

    if (!confirm(confirmMessage)) return;

    try {
      const userIds = Array.from(selectedUsers);
      const response = await usersApi.bulkResetTFA(userIds);
      const result = response.data;

      if (result.failed_count > 0) {
        toast.error(`Reset 2FA for ${result.success_count} users, ${result.failed_count} failed`);
      } else {
        toast.success(`Successfully reset 2FA for ${result.success_count} user${result.success_count > 1 ? 's' : ''}`);
      }

      setSelectedUsers(new Set());
      fetchUsers();
    } catch (error) {
      console.error('Failed to reset 2FA:', error);
      toast.error('Failed to reset 2FA');
    }
  };

  const handleEnforceTFA = async () => {
    if (selectedUsers.size === 0) return;

    const confirmMessage = `Enforce 2FA for ${selectedUsers.size} user${selectedUsers.size > 1 ? 's' : ''}? They will be required to set up 2FA on next login.`;

    if (!confirm(confirmMessage)) return;

    try {
      const userIds = Array.from(selectedUsers);
      const response = await usersApi.bulkEnforceTFA(userIds);
      const result = response.data;

      if (result.failed_count > 0) {
        toast.error(`Enforced 2FA for ${result.success_count} users, ${result.failed_count} failed`);
      } else {
        toast.success(`Successfully enforced 2FA for ${result.success_count} user${result.success_count > 1 ? 's' : ''}`);
      }

      setSelectedUsers(new Set());
      fetchUsers();
    } catch (error) {
      console.error('Failed to enforce 2FA:', error);
      toast.error('Failed to enforce 2FA');
    }
  };

  const handleDisableTFA = async () => {
    if (selectedUsers.size === 0) return;

    const confirmMessage = `Disable 2FA requirement for ${selectedUsers.size} user${selectedUsers.size > 1 ? 's' : ''}?`;

    if (!confirm(confirmMessage)) return;

    try {
      const userIds = Array.from(selectedUsers);
      const response = await usersApi.bulkDisableTFA(userIds);
      const result = response.data;

      if (result.failed_count > 0) {
        toast.error(`Disabled 2FA for ${result.success_count} users, ${result.failed_count} failed`);
      } else {
        toast.success(`Successfully disabled 2FA requirement for ${result.success_count} user${result.success_count > 1 ? 's' : ''}`);
      }

      setSelectedUsers(new Set());
      fetchUsers();
    } catch (error) {
      console.error('Failed to disable 2FA:', error);
      toast.error('Failed to disable 2FA requirement');
    }
  };

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
      case 'super_admin':
        return <Badge className="bg-purple-600"><ShieldCheck className="h-3 w-3 mr-1" />Super Admin</Badge>;
      case 'tenant_admin':
        return <Badge className="bg-blue-600"><UserCog className="h-3 w-3 mr-1" />Tenant Admin</Badge>;
      case 'tenant_user':
        return <Badge variant="secondary"><User className="h-3 w-3 mr-1" />User</Badge>;
      default:
        return <Badge variant="secondary">{type}</Badge>;
    }
  };

  const typeTabs = [
    { id: 'all', label: 'All Users', count: roleCounts.super_admin + roleCounts.tenant_admin + roleCounts.tenant_user },
    { id: 'super_admin', label: 'Super Admins', count: roleCounts.super_admin },
    { id: 'tenant_admin', label: 'Tenant Admins', count: roleCounts.tenant_admin },
    { id: 'tenant_user', label: 'Tenant Users', count: roleCounts.tenant_user },
  ];

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">User Management</h1>
          <p className="text-muted-foreground">
            Manage users, capabilities, and access groups across all tenants
          </p>
          <p className="text-sm text-amber-600 mt-1">
            GT AI OS Community Edition: Limited to 5 users per tenant
          </p>
        </div>
        <div className="flex space-x-2">
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
      <div className="grid grid-cols-1 md:grid-cols-1 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total Users</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{roleCounts.super_admin + roleCounts.tenant_admin + roleCounts.tenant_user}</div>
            <p className="text-xs text-muted-foreground">
              {users.filter(u => u.status === 'active').length} active on this page
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Type Tabs */}
      <div className="flex space-x-2 border-b">
        {typeTabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => handleTypeFilterChange(tab.id)}
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
            placeholder="Search users by name, email, or tenant... (Press Enter)"
            value={searchInput}
            onChange={(e) => setSearchInput((e as React.ChangeEvent<HTMLInputElement>).target.value)}
            onKeyPress={handleSearchKeyPress}
            className="pl-10"
          />
        </div>
        <Button variant="secondary" onClick={handleSearch}>
          <Search className="h-4 w-4 mr-2" />
          Search
        </Button>
      </div>

      {/* Bulk Actions */}
      {selectedUsers.size > 0 && (
        <Card className="bg-muted/50">
          <CardContent className="flex items-center justify-between py-3">
            <span className="text-sm">
              {selectedUsers.size} user{selectedUsers.size > 1 ? 's' : ''} selected
            </span>
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" size="sm" onClick={handleResetTFA}>
                <RotateCcw className="h-4 w-4 mr-2" />
                Reset 2FA
              </Button>
              <Button variant="default" size="sm" onClick={handleEnforceTFA}>
                <ShieldCheck className="h-4 w-4 mr-2" />
                Enforce 2FA
              </Button>
              <Button variant="secondary" size="sm" onClick={handleDisableTFA}>
                <ShieldOff className="h-4 w-4 mr-2" />
                Disable 2FA
              </Button>
              <Button variant="destructive" size="sm" onClick={handleDeleteSelected}>
                <Trash2 className="h-4 w-4 mr-2" />
                Delete Selected
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
                            handleSelectAll();
                          } else {
                            setSelectedUsers(new Set());
                          }
                        }}
                        checked={selectedUsers.size > 0 && selectedUsers.size === totalUsers}
                      />
                    </th>
                    <th className="p-4 text-left font-medium">User</th>
                    <th className="p-4 text-left font-medium">Type</th>
                    <th className="p-4 text-left font-medium">Tenant</th>
                    <th className="p-4 text-left font-medium">Status</th>
                    <th className="p-4 text-left font-medium">2FA</th>
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
                        {user.tfa_required && user.tfa_enabled ? (
                          <Badge variant="default" className="bg-green-600">
                            <ShieldCheck className="h-3 w-3 mr-1" />
                            Enforced & Configured
                          </Badge>
                        ) : user.tfa_required && !user.tfa_enabled ? (
                          <Badge variant="default" className="bg-orange-500">
                            <AlertTriangle className="h-3 w-3 mr-1" />
                            Enforced (Pending)
                          </Badge>
                        ) : !user.tfa_required && user.tfa_enabled ? (
                          <Badge variant="default" className="bg-green-500">
                            <ShieldCheck className="h-3 w-3 mr-1" />
                            Enabled
                          </Badge>
                        ) : (
                          <Badge variant="secondary">
                            <Lock className="h-3 w-3 mr-1" />
                            Disabled
                          </Badge>
                        )}
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

      {/* Pagination */}
      {!loading && totalUsers > 0 && (
        <div className="flex items-center justify-between">
          <div className="text-sm text-muted-foreground">
            Showing {((currentPage - 1) * limit) + 1} to {Math.min(currentPage * limit, totalUsers)} of {totalUsers} users
          </div>
          <div className="flex items-center space-x-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
              disabled={currentPage === 1}
            >
              Previous
            </Button>
            <div className="flex items-center space-x-1">
              {Array.from({ length: Math.ceil(totalUsers / limit) }, (_, i) => i + 1)
                .filter(page => {
                  // Show first page, last page, current page, and pages around current
                  const totalPages = Math.ceil(totalUsers / limit);
                  return page === 1 ||
                         page === totalPages ||
                         (page >= currentPage - 1 && page <= currentPage + 1);
                })
                .map((page, index, array) => {
                  // Add ellipsis if there's a gap
                  const showEllipsisBefore = index > 0 && page - array[index - 1] > 1;
                  return (
                    <div key={page} className="flex items-center">
                      {showEllipsisBefore && <span className="px-2">...</span>}
                      <Button
                        variant={currentPage === page ? "default" : "ghost"}
                        size="sm"
                        onClick={() => setCurrentPage(page)}
                        className="min-w-[2.5rem]"
                      >
                        {page}
                      </Button>
                    </div>
                  );
                })}
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setCurrentPage(prev => Math.min(Math.ceil(totalUsers / limit), prev + 1))}
              disabled={currentPage >= Math.ceil(totalUsers / limit)}
            >
              Next
            </Button>
          </div>
        </div>
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