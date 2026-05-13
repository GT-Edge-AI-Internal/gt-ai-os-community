'use client';

import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { X, Edit, Trash2, Save, Plus } from 'lucide-react';
import { cn } from '@/lib/utils';
import { CustomCategory, getCustomCategories, saveCustomCategories } from '@/services/user';

interface CategoryManagerProps {
  isOpen: boolean;
  onClose: () => void;
  onCategoriesUpdated?: () => void;
}

export function CategoryManager({ isOpen, onClose, onCategoriesUpdated }: CategoryManagerProps) {
  const [categories, setCategories] = useState<CustomCategory[]>([]);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editName, setEditName] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  // Load categories when modal opens
  useEffect(() => {
    if (isOpen) {
      loadCategories();
    }
  }, [isOpen]);

  const loadCategories = async () => {
    setIsLoading(true);
    try {
      const response = await getCustomCategories();
      if (response.data?.categories) {
        setCategories(response.data.categories);
      }
    } catch (error) {
      console.error('Failed to load custom categories:', error);
      alert('Failed to load categories. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await saveCustomCategories(categories);
      onCategoriesUpdated?.();
      onClose();
    } catch (error) {
      console.error('Failed to save categories:', error);
      alert('Failed to save categories. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleEdit = (index: number) => {
    setEditingIndex(index);
    setEditName(categories[index].name);
    setEditDescription(categories[index].description);
  };

  const handleSaveEdit = () => {
    if (!editName.trim()) {
      alert('Category name cannot be empty');
      return;
    }

    const trimmedName = editName.trim(); // Keep user's exact casing

    // Check for duplicates (case-insensitive, excluding current item)
    const isDuplicate = categories.some((cat, idx) =>
      idx !== editingIndex && cat.name.toLowerCase() === trimmedName.toLowerCase()
    );

    if (isDuplicate) {
      alert('A category with this name already exists');
      return;
    }

    const updated = [...categories];
    updated[editingIndex!] = {
      name: trimmedName,
      description: editDescription.trim(),
      created_at: categories[editingIndex!].created_at
    };
    setCategories(updated);
    setEditingIndex(null);
    setEditName('');
    setEditDescription('');
  };

  const handleCancelEdit = () => {
    setEditingIndex(null);
    setEditName('');
    setEditDescription('');
  };

  const handleDelete = (index: number) => {
    if (confirm(`Are you sure you want to delete the "${categories[index].name}" category?`)) {
      const updated = categories.filter((_, idx) => idx !== index);
      setCategories(updated);
    }
  };

  if (!isOpen) return null;
  if (typeof window === 'undefined') return null;

  return createPortal(
    <AnimatePresence>
      <motion.div
        key="backdrop"
        className="fixed inset-0 bg-black/50 backdrop-blur-sm z-[1001]"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      />

      <motion.div
        key="modal"
        className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-2xl bg-gt-white rounded-lg shadow-2xl z-[1002]"
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Manage Categories</h2>
            <p className="text-gray-600 mt-1">Edit or delete your custom agent categories</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 max-h-[60vh] overflow-y-auto">
          {isLoading ? (
            <div className="text-center py-8 text-gray-500">Loading categories...</div>
          ) : categories.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              No custom categories yet. Create one in the agent configuration panel.
            </div>
          ) : (
            <div className="space-y-3">
              {categories.map((category, index) => (
                <div
                  key={index}
                  className="border rounded-lg p-4 hover:border-gray-300 transition-colors"
                >
                  {editingIndex === index ? (
                    // Edit mode
                    <div className="space-y-3">
                      <div className="space-y-2">
                        <Label>Category Name</Label>
                        <Input
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          placeholder="Enter category name..."
                          autoFocus
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>Description</Label>
                        <Textarea
                          value={editDescription}
                          onChange={(e) => setEditDescription(e.target.value)}
                          placeholder="Enter category description..."
                          rows={2}
                        />
                      </div>
                      <div className="flex gap-2 justify-end">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleCancelEdit}
                        >
                          Cancel
                        </Button>
                        <Button
                          size="sm"
                          onClick={handleSaveEdit}
                          className="bg-gt-green hover:bg-gt-green/90"
                        >
                          <Save className="w-4 h-4 mr-2" />
                          Save
                        </Button>
                      </div>
                    </div>
                  ) : (
                    // View mode
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <h3 className="font-semibold text-gray-900">
                          {category.name}
                        </h3>
                        <p className="text-sm text-gray-600 mt-1">
                          {category.description}
                        </p>
                      </div>
                      <div className="flex gap-2 ml-4">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleEdit(index)}
                          className="text-blue-600 hover:text-blue-700 hover:bg-blue-50"
                        >
                          <Edit className="w-4 h-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDelete(index)}
                          className="text-red-600 hover:text-red-700 hover:bg-red-50"
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 p-6 border-t">
          <Button
            variant="outline"
            onClick={onClose}
            disabled={isSaving}
          >
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={isSaving || editingIndex !== null}
            className="bg-gt-green hover:bg-gt-green/90"
          >
            {isSaving ? 'Saving...' : 'Save Changes'}
          </Button>
        </div>
      </motion.div>
    </AnimatePresence>,
    document.body
  );
}
