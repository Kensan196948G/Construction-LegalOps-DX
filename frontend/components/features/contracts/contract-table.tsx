"use client";

import * as React from "react";
import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type ColumnFiltersState,
  type SortingState,
} from "@tanstack/react-table";
import { ArrowUpDown, Search } from "lucide-react";
import Link from "next/link";

import { cn } from "@/components/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  ContractStatusBadge,
  type ContractStatus,
} from "@/components/features/contracts/contract-status-badge";

export interface ContractRow {
  id: string;
  title: string;
  counterparty: string;
  status: ContractStatus;
  riskScore?: number;
  effectiveDate?: string;
  expiresAt?: string;
  owner?: string;
}

export interface ContractTableProps {
  data: ContractRow[];
  isLoading?: boolean;
  /** クリックされた行の詳細リンク先 (デフォルトで /contracts/[id]) */
  getRowHref?: (row: ContractRow) => string;
  className?: string;
}

const STATUS_OPTIONS: { value: ContractStatus | "all"; label: string }[] = [
  { value: "all", label: "すべてのステータス" },
  { value: "draft", label: "下書き" },
  { value: "in_review", label: "レビュー中" },
  { value: "approved", label: "承認済み" },
  { value: "expired", label: "期限切れ" },
  { value: "archived", label: "アーカイブ" },
];

export function ContractTable({
  data,
  isLoading = false,
  getRowHref = (row) => `/contracts/${row.id}`,
  className,
}: ContractTableProps) {
  const [sorting, setSorting] = React.useState<SortingState>([]);
  const [columnFilters, setColumnFilters] = React.useState<ColumnFiltersState>(
    []
  );
  const [globalFilter, setGlobalFilter] = React.useState("");

  const columns = React.useMemo<ColumnDef<ContractRow>[]>(
    () => [
      {
        accessorKey: "title",
        header: ({ column }) => (
          <Button
            variant="ghost"
            size="sm"
            className="-ml-3 h-8"
            onClick={() =>
              column.toggleSorting(column.getIsSorted() === "asc")
            }
          >
            契約名
            <ArrowUpDown className="ml-2 h-3.5 w-3.5" />
          </Button>
        ),
        cell: ({ row }) => (
          <Link
            href={getRowHref(row.original)}
            className="font-medium text-foreground hover:underline"
          >
            {row.original.title}
          </Link>
        ),
      },
      {
        accessorKey: "counterparty",
        header: "取引先",
        cell: ({ row }) => (
          <span className="text-muted-foreground">
            {row.original.counterparty}
          </span>
        ),
      },
      {
        accessorKey: "status",
        header: "ステータス",
        filterFn: (row, _id, value) =>
          value === "all" || row.original.status === value,
        cell: ({ row }) => (
          <ContractStatusBadge status={row.original.status} />
        ),
      },
      {
        accessorKey: "riskScore",
        header: "リスク",
        cell: ({ row }) => {
          const score = row.original.riskScore;
          if (score == null) return <span className="text-muted-foreground">—</span>;
          const tone =
            score >= 70
              ? "text-rose-600"
              : score >= 40
                ? "text-amber-600"
                : "text-emerald-600";
          return <span className={cn("font-mono text-sm", tone)}>{score}</span>;
        },
      },
      {
        accessorKey: "expiresAt",
        header: "満了日",
        cell: ({ row }) => (
          <span className="font-mono text-xs text-muted-foreground">
            {row.original.expiresAt ?? "—"}
          </span>
        ),
      },
      {
        accessorKey: "owner",
        header: "担当",
        cell: ({ row }) => row.original.owner ?? "—",
      },
    ],
    [getRowHref]
  );

  const table = useReactTable({
    data,
    columns,
    state: { sorting, columnFilters, globalFilter },
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onGlobalFilterChange: setGlobalFilter,
    globalFilterFn: "includesString",
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize: 20 } },
  });

  const statusFilter =
    (columnFilters.find((f) => f.id === "status")?.value as
      | ContractStatus
      | "all"
      | undefined) ?? "all";

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative w-full sm:max-w-xs">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={globalFilter}
            onChange={(e) => setGlobalFilter(e.target.value)}
            placeholder="契約名・取引先を検索"
            className="pl-9"
            aria-label="契約検索"
          />
        </div>
        <div className="w-full sm:w-56">
          <Select
            value={statusFilter}
            onValueChange={(v) =>
              table.getColumn("status")?.setFilterValue(v)
            }
          >
            <SelectTrigger aria-label="ステータスで絞り込み">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {STATUS_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((hg) => (
              <TableRow key={hg.id}>
                {hg.headers.map((h) => (
                  <TableHead key={h.id}>
                    {h.isPlaceholder
                      ? null
                      : flexRender(h.column.columnDef.header, h.getContext())}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={columns.length} className="h-24 text-center">
                  読み込み中...
                </TableCell>
              </TableRow>
            ) : table.getRowModel().rows.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="h-24 text-center text-muted-foreground"
                >
                  該当する契約はありません
                </TableCell>
              </TableRow>
            ) : (
              table.getRowModel().rows.map((row) => (
                <TableRow key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          {table.getFilteredRowModel().rows.length} 件中{" "}
          {table.getState().pagination.pageIndex *
            table.getState().pagination.pageSize +
            1}
          –
          {Math.min(
            (table.getState().pagination.pageIndex + 1) *
              table.getState().pagination.pageSize,
            table.getFilteredRowModel().rows.length
          )}{" "}
          件を表示
        </span>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
          >
            前へ
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
          >
            次へ
          </Button>
        </div>
      </div>
    </div>
  );
}

export default ContractTable;
