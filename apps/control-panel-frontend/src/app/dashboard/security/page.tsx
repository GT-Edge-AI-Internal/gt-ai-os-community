'use client';

import { useEffect, useState } from 'react';
import { Shield, Lock, AlertTriangle, UserCheck, Activity, FileText, Key, Loader2, Eye, CheckCircle, XCircle } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { securityApi } from '@/lib/api';
import toast from 'react-hot-toast';

interface SecurityEvent {
  id: number;
  timestamp: string;
  event_type: string;
  severity: string;
  user: string;
  ip_address: string;
  description: string;
  status: string;
}

interface AccessLog {
  id: number;
  timestamp: string;
  user_email: string;
  action: string;
  resource: string;
  result: string;
  ip_address: string;
}

interface SecurityPolicy {
  id: number;
  name: string;
  type: string;
  status: string;
  last_updated: string;
  violations: number;
}

export default function SecurityPage() {
  const [securityEvents, setSecurityEvents] = useState<SecurityEvent[]>([]);
  const [accessLogs, setAccessLogs] = useState<AccessLog[]>([]);
  const [policies, setPolicies] = useState<SecurityPolicy[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedSeverity, setSelectedSeverity] = useState('all');
  const [selectedTimeRange, setSelectedTimeRange] = useState('24h');
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    fetchSecurityData();
  }, [selectedSeverity, selectedTimeRange]);

  const fetchSecurityData = async () => {
    try {
      setIsLoading(true);
      
      // Fetch all security data in parallel
      const [eventsResponse, logsResponse, policiesResponse] = await Promise.all([
        securityApi.getSecurityEvents(1, 20, selectedSeverity === 'all' ? undefined : selectedSeverity, selectedTimeRange).catch(() => null),
        securityApi.getAccessLogs(1, 20, selectedTimeRange).catch(() => null),
        securityApi.getSecurityPolicies().catch(() => null)
      ]);

      // Set data from API responses or empty defaults
      setSecurityEvents(eventsResponse?.data?.events || []);
      setAccessLogs(logsResponse?.data?.access_logs || []);
      setPolicies(policiesResponse?.data?.policies || []);
    } catch (error) {
      console.error('Failed to fetch security data:', error);
      toast.error('Failed to load security data');
      
      // Set empty arrays on error
      setSecurityEvents([]);
      setAccessLogs([]);
      setPolicies([]);
    } finally {
      setIsLoading(false);
    }
  };

  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case 'critical':
        return <Badge variant="destructive">Critical</Badge>;
      case 'warning':
        return <Badge variant="default" className="bg-yellow-600">Warning</Badge>;
      case 'info':
        return <Badge variant="secondary">Info</Badge>;
      default:
        return <Badge variant="secondary">{severity}</Badge>;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'resolved':
        return <Badge variant="default" className="bg-green-600">Resolved</Badge>;
      case 'investigating':
        return <Badge variant="default" className="bg-blue-600">Investigating</Badge>;
      case 'acknowledged':
        return <Badge variant="default" className="bg-yellow-600">Acknowledged</Badge>;
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  const getResultBadge = (result: string) => {
    return result === 'success' ? (
      <Badge variant="default" className="bg-green-600">Success</Badge>
    ) : (
      <Badge variant="destructive">Denied</Badge>
    );
  };

  const getEventIcon = (eventType: string) => {
    switch (eventType) {
      case 'login_attempt':
        return <UserCheck className="h-4 w-4" />;
      case 'permission_denied':
        return <Lock className="h-4 w-4" />;
      case 'brute_force_attempt':
        return <AlertTriangle className="h-4 w-4" />;
      case 'api_rate_limit':
        return <Activity className="h-4 w-4" />;
      default:
        return <Shield className="h-4 w-4" />;
    }
  };

  const filteredEvents = securityEvents.filter(event => {
    if (selectedSeverity !== 'all' && event.severity !== selectedSeverity) {
      return false;
    }
    if (searchQuery && !event.description.toLowerCase().includes(searchQuery.toLowerCase()) &&
        !event.user.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false;
    }
    return true;
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[600px]">
        <div className="flex items-center space-x-2">
          <Loader2 className="h-6 w-6 animate-spin" />
          <span className="text-muted-foreground">Loading security data...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Security Center</h1>
          <p className="text-muted-foreground">
            Monitor security events, access logs, and policy compliance
          </p>
        </div>
        <Button variant="secondary">
          <FileText className="mr-2 h-4 w-4" />
          Export Report
        </Button>
      </div>

      {/* Security Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center">
              <Shield className="h-4 w-4 mr-2" />
              Security Score
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">92/100</div>
            <p className="text-xs text-muted-foreground mt-1">Excellent</p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center">
              <AlertTriangle className="h-4 w-4 mr-2" />
              Active Threats
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">1</div>
            <p className="text-xs text-muted-foreground mt-1">Requires attention</p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center">
              <UserCheck className="h-4 w-4 mr-2" />
              Failed Logins
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">3</div>
            <p className="text-xs text-muted-foreground mt-1">Last 24 hours</p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center">
              <Lock className="h-4 w-4 mr-2" />
              Policy Violations
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-yellow-600">15</div>
            <p className="text-xs text-muted-foreground mt-1">This week</p>
          </CardContent>
        </Card>
      </div>

      {/* Security Events */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Security Events</CardTitle>
              <CardDescription>Real-time security event monitoring</CardDescription>
            </div>
            <div className="flex items-center space-x-2">
              <Input
                placeholder="Search events..."
                value={searchQuery}
                onChange={(e) => setSearchQuery((e as React.ChangeEvent<HTMLInputElement>).target.value)}
                className="w-[200px]"
              />
              <Select value={selectedSeverity} onValueChange={setSelectedSeverity}>
                <SelectTrigger className="w-[130px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Severities</SelectItem>
                  <SelectItem value="critical">Critical</SelectItem>
                  <SelectItem value="warning">Warning</SelectItem>
                  <SelectItem value="info">Info</SelectItem>
                </SelectContent>
              </Select>
              <Select value={selectedTimeRange} onValueChange={setSelectedTimeRange}>
                <SelectTrigger className="w-[120px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="1h">Last Hour</SelectItem>
                  <SelectItem value="24h">Last 24h</SelectItem>
                  <SelectItem value="7d">Last 7 Days</SelectItem>
                  <SelectItem value="30d">Last 30 Days</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Time</TableHead>
                <TableHead>Event</TableHead>
                <TableHead>Severity</TableHead>
                <TableHead>User</TableHead>
                <TableHead>IP Address</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredEvents.map((event) => (
                <TableRow key={event.id}>
                  <TableCell className="text-sm">
                    {new Date(event.timestamp).toLocaleString()}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center space-x-2">
                      {getEventIcon(event.event_type)}
                      <span className="text-sm">{event.event_type.replace('_', ' ')}</span>
                    </div>
                  </TableCell>
                  <TableCell>{getSeverityBadge(event.severity)}</TableCell>
                  <TableCell className="text-sm">{event.user}</TableCell>
                  <TableCell className="text-sm font-mono">{event.ip_address}</TableCell>
                  <TableCell className="text-sm">{event.description}</TableCell>
                  <TableCell>{getStatusBadge(event.status)}</TableCell>
                  <TableCell>
                    <Button size="sm" variant="secondary">
                      <Eye className="h-3 w-3" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Access Logs */}
        <Card>
          <CardHeader>
            <CardTitle>Access Logs</CardTitle>
            <CardDescription>Recent access attempts and API calls</CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Time</TableHead>
                  <TableHead>User</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Resource</TableHead>
                  <TableHead>Result</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {accessLogs.map((log) => (
                  <TableRow key={log.id}>
                    <TableCell className="text-sm">
                      {new Date(log.timestamp).toLocaleTimeString()}
                    </TableCell>
                    <TableCell className="text-sm">{log.user_email.split('@')[0]}</TableCell>
                    <TableCell className="text-sm font-medium">{log.action}</TableCell>
                    <TableCell className="text-sm font-mono text-xs">{log.resource}</TableCell>
                    <TableCell>{getResultBadge(log.result)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        {/* Security Policies */}
        <Card>
          <CardHeader>
            <CardTitle>Security Policies</CardTitle>
            <CardDescription>Active security policies and compliance</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {policies.map((policy) => (
                <div key={policy.id} className="border rounded-lg p-3">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center space-x-2">
                      <Key className="h-4 w-4 text-muted-foreground" />
                      <span className="font-medium">{policy.name}</span>
                    </div>
                    {policy.status === 'active' ? (
                      <CheckCircle className="h-4 w-4 text-green-600" />
                    ) : (
                      <XCircle className="h-4 w-4 text-red-600" />
                    )}
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Type: {policy.type.replace('_', ' ')}</span>
                    {policy.violations > 0 && (
                      <Badge variant="destructive" className="text-xs">
                        {policy.violations} violations
                      </Badge>
                    )}
                  </div>
                  <div className="text-xs text-muted-foreground mt-1">
                    Updated {new Date(policy.last_updated).toLocaleDateString()}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}