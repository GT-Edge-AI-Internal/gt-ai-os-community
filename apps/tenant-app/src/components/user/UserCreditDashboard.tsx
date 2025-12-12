"use client";

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from '@/components/ui/table';
import { 
  Zap, 
  TrendingUp, 
  Calendar,
  BarChart3,
  AlertTriangle,
  RefreshCw,
  Download,
  Info
} from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';
import { formatDateOnly, formatTime } from '@/lib/utils';

interface UserCreditAllocation {
  user_id: string;
  allocated_credits: number;
  used_credits: number;
  remaining_credits: number;
  monthly_limit: number;
  daily_usage_limit: number;
  role: string;
  allocation_renewed_date: string;
  next_renewal_date: string;
}

interface CreditUsage {
  date: string;
  resource_type: string;
  resource_name: string;
  credits_used: number;
  dollar_equivalent: number;
  usage_context: string;
}

interface UsageSummary {
  total_credits_used_today: number;
  total_credits_used_this_week: number;
  total_credits_used_this_month: number;
  top_resource_usage: Array<{
    resource_name: string;
    credits_used: number;
    percentage_of_total: number;
  }>;
  daily_average: number;
  projected_monthly_usage: number;
}

export default function UserCreditDashboard() {
  const [userAllocation, setUserAllocation] = useState<UserCreditAllocation | null>(null);
  const [recentUsage, setRecentUsage] = useState<CreditUsage[]>([]);
  const [usageSummary, setUsageSummary] = useState<UsageSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState('7d');
  const { toast } = useToast();

  const fetchUserCreditData = async () => {
    try {
      setLoading(true);
      
      // Mock data - replace with real API calls
      const mockAllocation: UserCreditAllocation = {
        user_id: 'current-user',
        allocated_credits: 1500,
        used_credits: 387,
        remaining_credits: 1113,
        monthly_limit: 1500,
        daily_usage_limit: 100,
        role: 'developer',
        allocation_renewed_date: '2025-01-01T00:00:00Z',
        next_renewal_date: '2025-02-01T00:00:00Z'
      };

      const mockUsage: CreditUsage[] = [
        {
          date: '2025-01-09T14:30:00Z',
          resource_type: 'AI Model',
          resource_name: 'llama-3.3-70b-versatile',
          credits_used: 12,
          dollar_equivalent: 0.12,
          usage_context: 'Code analysis request'
        },
        {
          date: '2025-01-09T13:15:00Z',
          resource_type: 'AI Model',
          resource_name: 'llama-3.1-8b-instant',
          credits_used: 8,
          dollar_equivalent: 0.08,
          usage_context: 'Document summarization'
        },
        {
          date: '2025-01-09T12:00:00Z',
          resource_type: 'Vector Search',
          resource_name: 'Document Search',
          credits_used: 2,
          dollar_equivalent: 0.02,
          usage_context: 'Knowledge base query'
        },
        {
          date: '2025-01-08T16:45:00Z',
          resource_type: 'AI Model',
          resource_name: 'mixtral-8x7b-32768',
          credits_used: 5,
          dollar_equivalent: 0.05,
          usage_context: 'Chat conversation'
        }
      ];

      const mockSummary: UsageSummary = {
        total_credits_used_today: 22,
        total_credits_used_this_week: 89,
        total_credits_used_this_month: 387,
        top_resource_usage: [
          { resource_name: 'llama-3.3-70b-versatile', credits_used: 156, percentage_of_total: 40.3 },
          { resource_name: 'llama-3.1-8b-instant', credits_used: 98, percentage_of_total: 25.3 },
          { resource_name: 'mixtral-8x7b-32768', credits_used: 87, percentage_of_total: 22.5 },
          { resource_name: 'Document Search', credits_used: 46, percentage_of_total: 11.9 }
        ],
        daily_average: 12.5,
        projected_monthly_usage: 385
      };

      setUserAllocation(mockAllocation);
      setRecentUsage(mockUsage);
      setUsageSummary(mockSummary);
    } catch (error) {
      console.error('Failed to fetch user credit data:', error);
      toast({
        title: "Error Loading Data",
        description: "Failed to load your credit usage information",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleExportUsage = () => {
    // TODO: Implement CSV export of usage history
    toast({
      title: "Export Started",
      description: "Your usage history is being prepared for download",
    });
  };

  useEffect(() => {
    fetchUserCreditData();
  }, [timeRange]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="flex items-center space-x-2">
          <RefreshCw className="h-6 w-6 animate-spin" />
          <span className="text-muted-foreground">Loading your credit usage...</span>
        </div>
      </div>
    );
  }

  const usagePercentage = userAllocation 
    ? (userAllocation.used_credits / userAllocation.allocated_credits) * 100 
    : 0;

  const projectedUsagePercentage = usageSummary && userAllocation
    ? (usageSummary.projected_monthly_usage / userAllocation.monthly_limit) * 100
    : 0;

  const dailyUsageToday = usageSummary?.total_credits_used_today || 0;
  const dailyUsagePercentage = userAllocation
    ? (dailyUsageToday / userAllocation.daily_usage_limit) * 100
    : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">My Infrastructure Credits</h1>
          <p className="text-muted-foreground">
            Track your personal credit allocation and usage
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleExportUsage}>
            <Download className="mr-2 h-4 w-4" />
            Export Usage
          </Button>
          <Button variant="outline" size="sm" onClick={fetchUserCreditData}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Credit Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Available Credits</CardTitle>
            <Zap className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {userAllocation?.remaining_credits.toLocaleString()}
            </div>
            <p className="text-xs text-muted-foreground">
              of {userAllocation?.allocated_credits.toLocaleString()} allocated
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Used This Month</CardTitle>
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{userAllocation?.used_credits.toLocaleString()}</div>
            <Progress value={usagePercentage} className="h-2 mt-2" />
            <p className="text-xs text-muted-foreground mt-1">
              {usagePercentage.toFixed(1)}% of monthly allocation
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Used Today</CardTitle>
            <Calendar className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{dailyUsageToday.toLocaleString()}</div>
            <Progress value={dailyUsagePercentage} className="h-2 mt-2" />
            <p className="text-xs text-muted-foreground mt-1">
              of {userAllocation?.daily_usage_limit} daily limit
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Projected Usage</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${projectedUsagePercentage > 100 ? 'text-red-600' : 'text-green-600'}`}>
              {usageSummary?.projected_monthly_usage.toLocaleString()}
            </div>
            <p className="text-xs text-muted-foreground">
              {projectedUsagePercentage.toFixed(1)}% of monthly limit
            </p>
          </CardContent>
        </Card>
      </div>

      {/* User Role and Limits Info */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Info className="w-5 h-5" />
            Credit Allocation Details
          </CardTitle>
          <CardDescription>
            Your credit limits based on role and tenant policies
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div>
              <h4 className="font-medium mb-2">Role & Limits</h4>
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="capitalize">{userAllocation?.role}</Badge>
                  <span className="text-sm text-muted-foreground">role</span>
                </div>
                <p className="text-sm">
                  <span className="text-muted-foreground">Monthly Limit:</span> {userAllocation?.monthly_limit.toLocaleString()} credits
                </p>
                <p className="text-sm">
                  <span className="text-muted-foreground">Daily Limit:</span> {userAllocation?.daily_usage_limit} credits
                </p>
              </div>
            </div>
            
            <div>
              <h4 className="font-medium mb-2">Renewal Schedule</h4>
              <div className="space-y-2">
                <p className="text-sm">
                  <span className="text-muted-foreground">Last Renewed:</span><br />
                  {formatDateOnly(userAllocation?.allocation_renewed_date || '')}
                </p>
                <p className="text-sm">
                  <span className="text-muted-foreground">Next Renewal:</span><br />
                  {formatDateOnly(userAllocation?.next_renewal_date || '')}
                </p>
              </div>
            </div>
            
            <div>
              <h4 className="font-medium mb-2">Usage Insights</h4>
              <div className="space-y-2">
                <p className="text-sm">
                  <span className="text-muted-foreground">Daily Average:</span> {usageSummary?.daily_average} credits
                </p>
                <p className="text-sm">
                  <span className="text-muted-foreground">Weekly Usage:</span> {usageSummary?.total_credits_used_this_week} credits
                </p>
              </div>
            </div>
          </div>

          {projectedUsagePercentage > 90 && (
            <div className="mt-4 flex items-center gap-2 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
              <AlertTriangle className="h-4 w-4 text-yellow-600" />
              <span className="text-sm text-yellow-800">
                Warning: Your projected usage may exceed your monthly allocation. Consider optimizing your resource usage.
              </span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Top Resource Usage */}
      <Card>
        <CardHeader>
          <CardTitle>Resource Usage Breakdown</CardTitle>
          <CardDescription>
            Your top resource consumers this month
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {usageSummary?.top_resource_usage.map((resource, index) => (
              <div key={resource.resource_name} className="flex items-center justify-between p-3 border rounded-lg">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-sm font-medium">
                    {index + 1}
                  </div>
                  <div>
                    <div className="font-medium">{resource.resource_name}</div>
                    <div className="text-sm text-muted-foreground">
                      {resource.credits_used.toLocaleString()} credits used
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-medium">{resource.percentage_of_total.toFixed(1)}%</div>
                  <div className="text-sm text-muted-foreground">
                    ${(resource.credits_used * 0.01).toFixed(2)} USD
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Recent Usage History */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Usage History</CardTitle>
          <CardDescription>
            Your most recent resource usage activity
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date & Time</TableHead>
                <TableHead>Resource</TableHead>
                <TableHead>Context</TableHead>
                <TableHead>Credits Used</TableHead>
                <TableHead>Cost (USD)</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {recentUsage.map((usage, index) => (
                <TableRow key={index}>
                  <TableCell>
                    <div>
                      <div className="font-medium">
                        {formatDateOnly(usage.date)}
                      </div>
                      <div className="text-sm text-muted-foreground">
                        {formatTime(usage.date)}
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>
                    <div>
                      <div className="font-medium">{usage.resource_name}</div>
                      <div className="text-sm text-muted-foreground">
                        <Badge variant="outline" className="text-xs">
                          {usage.resource_type}
                        </Badge>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="text-sm">{usage.usage_context}</TableCell>
                  <TableCell className="font-medium">{usage.credits_used}</TableCell>
                  <TableCell className="text-green-600 font-medium">
                    ${usage.dollar_equivalent.toFixed(2)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Credit Information */}
      <Card className="bg-blue-50 border-blue-200">
        <CardHeader>
          <CardTitle className="text-blue-800">Understanding Infrastructure Credits</CardTitle>
        </CardHeader>
        <CardContent className="text-blue-700 space-y-2">
          <ul className="list-disc list-inside space-y-1 text-sm">
            <li><strong>1 Credit ≈ $0.01 USD</strong> - Credits abstract electrical, network, and inference costs</li>
            <li><strong>AI Models:</strong> 1-15 credits per request (varies by model complexity)</li>
            <li><strong>Vector Search:</strong> 0.1-2 credits per query</li>
            <li><strong>Document Processing:</strong> 0.5 credits per MB processed</li>
            <li><strong>API Calls:</strong> 0.1 credits per request</li>
            <li><strong>Storage:</strong> 1 credit per 1000 documents stored monthly</li>
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}