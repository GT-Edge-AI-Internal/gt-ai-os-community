'use client';

import { TestLayout } from '@/components/layout/test-layout';
import { useState, useEffect } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { 
  Plus, Folder, FolderOpen, Users, Calendar, 
  BarChart3, CheckCircle2, Clock, AlertCircle,
  MoreVertical, Share2, Archive
} from 'lucide-react';
import { mockApi } from '@/lib/mock-api';
import { formatDateOnly } from '@/lib/utils';

export default function TestProjectsPage() {
  const [projects, setProjects] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadProjects();
  }, []);

  const loadProjects = async () => {
    try {
      const data = await mockApi.projects.list();
      setProjects(data.projects);
    } catch (error) {
      console.error('Failed to load projects:', error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'active': return <Clock className="w-4 h-4 text-blue-600" />;
      case 'completed': return <CheckCircle2 className="w-4 h-4 text-green-600" />;
      case 'on_hold': return <AlertCircle className="w-4 h-4 text-yellow-600" />;
      default: return <Folder className="w-4 h-4 text-gray-400" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'bg-blue-100 text-blue-700';
      case 'completed': return 'bg-green-100 text-green-700';
      case 'on_hold': return 'bg-yellow-100 text-yellow-700';
      default: return 'bg-gray-100 text-gray-700';
    }
  };

  if (loading) {
    return (
      <TestLayout>
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-green-600"></div>
        </div>
      </TestLayout>
    );
  }

  return (
    <TestLayout>
      <div className="p-6">
        {/* Header */}
        <div className="mb-6">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Projects</h1>
              <p className="text-gray-600 mt-1">Manage your research and analysis projects</p>
            </div>
            <Button className="bg-green-600 hover:bg-green-700 text-white">
              <Plus className="w-4 h-4 mr-2" />
              New Project
            </Button>
          </div>
        </div>

        {/* Project Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <Card className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Active Projects</p>
                <p className="text-2xl font-bold text-gray-900">
                  {projects.filter(p => p.status === 'active').length}
                </p>
              </div>
              <Clock className="w-8 h-8 text-blue-500 opacity-50" />
            </div>
          </Card>

          <Card className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Completed</p>
                <p className="text-2xl font-bold text-gray-900">
                  {projects.filter(p => p.status === 'completed').length}
                </p>
              </div>
              <CheckCircle2 className="w-8 h-8 text-green-500 opacity-50" />
            </div>
          </Card>

          <Card className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Total Hours</p>
                <p className="text-2xl font-bold text-gray-900">
                  {projects.reduce((acc, p) => acc + (p.time_invested_minutes || 0), 0) / 60}h
                </p>
              </div>
              <BarChart3 className="w-8 h-8 text-purple-500 opacity-50" />
            </div>
          </Card>

          <Card className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Collaborators</p>
                <p className="text-2xl font-bold text-gray-900">
                  {projects.reduce((acc, p) => acc + (p.collaborators?.length || 0), 0)}
                </p>
              </div>
              <Users className="w-8 h-8 text-orange-500 opacity-50" />
            </div>
          </Card>
        </div>

        {/* Projects Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {projects.map((project) => (
            <Card key={project.id} className="hover:shadow-lg transition-shadow">
              <div className="p-6">
                {/* Project Header */}
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center">
                    {project.status === 'active' ? (
                      <FolderOpen className="w-5 h-5 text-green-600 mr-2" />
                    ) : (
                      <Folder className="w-5 h-5 text-gray-400 mr-2" />
                    )}
                    <h3 className="font-semibold text-gray-900">{project.name}</h3>
                  </div>
                  <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                    <MoreVertical className="w-4 h-4" />
                  </Button>
                </div>

                {/* Description */}
                <p className="text-sm text-gray-600 mb-4 line-clamp-2">
                  {project.description}
                </p>

                {/* Progress */}
                <div className="mb-4">
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-600">Progress</span>
                    <span className="font-medium">{project.completion_percentage}%</span>
                  </div>
                  <Progress value={project.completion_percentage} className="h-2" />
                </div>

                {/* Status and Type */}
                <div className="flex items-center gap-2 mb-4">
                  <Badge className={getStatusColor(project.status)}>
                    {project.status.replace('_', ' ')}
                  </Badge>
                  <Badge variant="secondary">
                    {project.project_type}
                  </Badge>
                </div>

                {/* Resources */}
                {project.linked_resources && project.linked_resources.length > 0 && (
                  <div className="mb-4">
                    <p className="text-xs text-gray-500 mb-2">Resources:</p>
                    <div className="flex flex-wrap gap-1">
                      {project.linked_resources.slice(0, 3).map((resource: string, idx: number) => (
                        <Badge key={idx} variant="secondary" className="text-xs">
                          {resource}
                        </Badge>
                      ))}
                      {project.linked_resources.length > 3 && (
                        <Badge variant="secondary" className="text-xs">
                          +{project.linked_resources.length - 3}
                        </Badge>
                      )}
                    </div>
                  </div>
                )}

                {/* Collaborators */}
                {project.collaborators && project.collaborators.length > 0 && (
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex -space-x-2">
                      {project.collaborators.slice(0, 3).map((collaborator: any, idx: number) => (
                        <div
                          key={idx}
                          className="w-8 h-8 rounded-full bg-gray-300 border-2 border-white flex items-center justify-center"
                        >
                          <span className="text-xs font-medium text-gray-600">
                            {collaborator.name.split(' ').map((n: string) => n[0]).join('')}
                          </span>
                        </div>
                      ))}
                      {project.collaborators.length > 3 && (
                        <div className="w-8 h-8 rounded-full bg-gray-200 border-2 border-white flex items-center justify-center">
                          <span className="text-xs font-medium text-gray-600">
                            +{project.collaborators.length - 3}
                          </span>
                        </div>
                      )}
                    </div>
                    <Share2 className="w-4 h-4 text-gray-400" />
                  </div>
                )}

                {/* Dates */}
                <div className="flex items-center justify-between text-xs text-gray-500 mb-4">
                  <div className="flex items-center">
                    <Calendar className="w-3 h-3 mr-1" />
                    Created {formatDateOnly(project.created_at)}
                  </div>
                  {project.last_activity && (
                    <span>Active {formatDateOnly(project.last_activity)}</span>
                  )}
                </div>

                {/* Actions */}
                <div className="flex gap-2">
                  <Button className="flex-1" variant="secondary">
                    Open Project
                  </Button>
                  {project.status === 'active' && (
                    <Button variant="ghost" size="sm" className="px-2">
                      <Archive className="w-4 h-4" />
                    </Button>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </TestLayout>
  );
}