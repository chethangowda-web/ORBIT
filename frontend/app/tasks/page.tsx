"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { Navbar } from "@/components/Navbar";
import { TaskTable } from "@/components/TaskTable";
import { SearchBar } from "@/components/SearchBar";
import { FilterBar } from "@/components/FilterBar";
import { Pagination } from "@/components/Pagination";
import { CreateTaskModal } from "@/components/CreateTaskModal";
import { User } from "@/types";

export default function TasksPage() {
  const queryClient = useQueryClient();
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Filters state
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");
  const [assigneeId, setAssigneeId] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = 10;

  // Fetch users for dropdown filter
  const { data: users = [] } = useQuery<User[]>({
    queryKey: ["users"],
    queryFn: () => api.users.list(),
  });

  // Fetch tasks with filters
  const { data: tasksData, isLoading } = useQuery({
    queryKey: ["tasks", { search, status, priority, assigneeId, page, pageSize }],
    queryFn: () =>
      api.tasks.list({
        q: search || undefined,
        status: status || undefined,
        priority: priority || undefined,
        assignee_id: assigneeId || undefined,
        page,
        page_size: pageSize,
      }),
  });

  // Complete mutation
  const completeMutation = useMutation({
    mutationFn: (id: string) => api.tasks.complete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.tasks.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
    },
  });

  const handleResetFilters = () => {
    setSearch("");
    setStatus("");
    setPriority("");
    setAssigneeId("");
    setPage(1);
  };

  return (
    <div className="flex-1 flex flex-col min-h-screen">
      <Navbar
        title="Tasks Management"
        onCreateTask={() => setIsModalOpen(true)}
      />

      <div className="p-6 space-y-5 flex-1 flex flex-col">
        {/* Controls: Search and Filters */}
        <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4 p-4 rounded-2xl glass-panel border border-slate-800/80">
          <SearchBar
            value={search}
            onChange={(val) => {
              setSearch(val);
              setPage(1);
            }}
            placeholder="Search by title, description, or tag..."
          />

          <FilterBar
            status={status}
            onStatusChange={(val) => {
              setStatus(val);
              setPage(1);
            }}
            priority={priority}
            onPriorityChange={(val) => {
              setPriority(val);
              setPage(1);
            }}
            assigneeId={assigneeId}
            onAssigneeChange={(val) => {
              setAssigneeId(val);
              setPage(1);
            }}
            users={users}
            onReset={handleResetFilters}
          />
        </div>

        {/* Task Table */}
        <div className="flex-1 flex flex-col justify-between">
          <TaskTable
            tasks={tasksData?.tasks || []}
            isLoading={isLoading}
            onCompleteTask={(id) => completeMutation.mutate(id)}
            onDeleteTask={(id) => {
              if (confirm("Are you sure you want to soft delete this task?")) {
                deleteMutation.mutate(id);
              }
            }}
          />

          {tasksData?.meta && (
            <Pagination
              meta={tasksData.meta}
              onPageChange={(p) => setPage(p)}
            />
          )}
        </div>
      </div>

      {/* Create Task Modal */}
      <CreateTaskModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={() => {
          queryClient.invalidateQueries({ queryKey: ["tasks"] });
        }}
      />
    </div>
  );
}
