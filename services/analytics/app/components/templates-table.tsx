import Link from 'next/link';
import { Package, ChevronRight } from 'lucide-react';
import type { TemplateMetrics } from '@/lib/types';
import { Tooltip } from './tooltip';

interface TemplatesTableProps {
  templates: TemplateMetrics[];
}

function getTeamCount(teamDistribution: Record<string, number>): number {
  return Object.keys(teamDistribution).length;
}

export function TemplatesTable({ templates }: TemplatesTableProps) {
  return (
    <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl border-2 border-slate-200 dark:border-slate-700 overflow-hidden">
      <div className="px-6 py-5 border-b border-slate-200 dark:border-slate-700">
        <h2 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
          <Package className="h-6 w-6 text-vector-magenta" />
          Templates
        </h2>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
          Click on a template to view team-specific details
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-slate-100 dark:bg-slate-800 border-b-2 border-vector-magenta/20 dark:border-vector-violet/30">
            <tr>
              <th className="px-6 py-4 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                Template
              </th>
              <th className="px-6 py-4 text-right text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                <Tooltip content="Number of unique teams using this template">
                  Teams
                </Tooltip>
              </th>
              <th className="px-6 py-4 text-right text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                <Tooltip content="Total number of workspaces created from this template">
                  Workspaces
                </Tooltip>
              </th>
              <th className="px-6 py-4 text-right text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                <Tooltip content="Number of workspaces with activity in the last 7 days">
                  Active
                </Tooltip>
              </th>
              <th className="px-6 py-4 text-right text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                <Tooltip content="Number of unique users who have used this template in the last 7 days">
                  Active Users
                </Tooltip>
              </th>
              <th className="px-6 py-4 text-right text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                <Tooltip content="Total accumulated time across all workspace sessions, from startup to shutdown">
                  Total Hours
                </Tooltip>
              </th>
              <th className="px-6 py-4 text-right text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                <Tooltip content="Total accumulated time when workspaces have active app connections (e.g., VS Code connected)" position="right">
                  Active Hours
                </Tooltip>
              </th>
              <th className="px-6 py-4 text-right text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                {/* Actions */}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
            {templates.map((template) => (
              <tr
                key={template.template_id}
                className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors group"
              >
                <td className="px-6 py-4">
                  <div className="flex items-center gap-3">
                    <div className="flex-shrink-0 h-10 w-10 rounded-lg bg-gradient-to-br from-vector-turquoise to-vector-cobalt flex items-center justify-center">
                      <Package className="h-5 w-5 text-white" />
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-slate-900 dark:text-white">
                        {template.template_display_name}
                      </div>
                      <div className="text-xs text-slate-500 dark:text-slate-400">
                        {template.template_name}
                      </div>
                    </div>
                  </div>
                </td>
                <td className="px-6 py-4 text-right text-sm">
                  <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-200 border border-slate-300 dark:border-slate-600">
                    {getTeamCount(template.team_distribution)}
                  </span>
                </td>
                <td className="px-6 py-4 text-right text-sm text-slate-700 dark:text-slate-300">
                  {template.total_workspaces}
                </td>
                <td className="px-6 py-4 text-right text-sm">
                  <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-vector-turquoise/10 text-vector-turquoise border border-vector-turquoise/30">
                    {template.active_workspaces}
                  </span>
                </td>
                <td className="px-6 py-4 text-right text-sm">
                  <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-vector-violet/10 text-vector-violet border border-vector-violet/30">
                    {template.unique_active_users}
                  </span>
                </td>
                <td className="px-6 py-4 text-right text-sm text-slate-700 dark:text-slate-300">
                  {template.total_workspace_hours.toLocaleString()}h
                </td>
                <td className="px-6 py-4 text-right text-sm">
                  <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800">
                    {template.total_active_hours.toLocaleString()}h
                  </span>
                </td>
                <td className="px-6 py-4 text-right">
                  <Link
                    href={`/template/${encodeURIComponent(template.template_name)}`}
                    className="inline-flex items-center gap-1 text-vector-magenta hover:text-vector-violet transition-colors"
                  >
                    <span className="text-sm font-medium">View Teams</span>
                    <ChevronRight className="h-4 w-4" />
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
