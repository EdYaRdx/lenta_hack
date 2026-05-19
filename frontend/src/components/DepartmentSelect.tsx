import { departments } from "../data/mock";
import type { Department } from "../types";
import { formatDepartment } from "../utils/format";

interface DepartmentSelectProps {
  value: Department;
  onChange: (value: Department) => void;
}

export function DepartmentSelect({ value, onChange }: DepartmentSelectProps) {
  return (
    <div className="department-field">
      <label htmlFor="department-select">Отдел и reference key</label>
      <select
        id="department-select"
        value={value}
        onChange={(event) => onChange(event.target.value as Department)}
      >
        {departments.map((department) => (
          <option key={department} value={department}>
            {department} - {formatDepartment(department)}
          </option>
        ))}
      </select>
      <span className="input-hint">Выбор позже попадет в input/&lt;run_id&gt;/name.json.</span>
    </div>
  );
}
