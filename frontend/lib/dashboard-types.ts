export type DashboardSummary = {
  today_appointments: number;
  upcoming_appointments: number;
  total_customers: number;
  active_staff: number;
};

export type DashboardAppointment = {
  id: number;
  customer_name: string;
  customer_phone: string;
  service_name: string;
  assigned_staff_name: string | null;
  start_at: string;
  end_at: string;
  status: string;
  source: string;
  notes: string | null;
};

export type AppointmentDetail = {
  id: number;
  customer_id: number;
  customer_name: string;
  customer_phone: string;
  customer_email: string | null;
  service_id: number;
  service_name: string;
  service_duration_minutes: number;
  assigned_staff_id: number | null;
  assigned_staff_name: string | null;
  start_at: string;
  end_at: string;
  status: string;
  source: string;
  notes: string | null;
  created_at: string;
};

export type AppointmentSlot = {
  start_at: string;
  end_at: string;
  available_staff: Array<{ id: number; name: string }>;
};

export type AppointmentAvailability = {
  date: string;
  service_id: number;
  service_duration_minutes: number;
  slots: AppointmentSlot[];
};

export type DashboardCustomer = {
  id: number;
  name: string;
  phone: string;
  email: string | null;
  appointment_count: number;
  upcoming_appointment_count: number;
  last_appointment_at: string | null;
  created_at: string;
};

export type DashboardStaffService = {
  id: number;
  name: string;
  duration_minutes: number;
};

export type DashboardStaffAvailability = {
  id: number;
  weekday: number;
  start_time: string;
  end_time: string;
  slot_duration_minutes: number;
  active: boolean;
};

export type DashboardStaff = {
  id: number;
  name: string;
  phone: string | null;
  email: string | null;
  active: boolean;
  services: DashboardStaffService[];
  availability: DashboardStaffAvailability[];
  upcoming_appointment_count: number;
  today_appointment_count: number;
};

export type ServiceOption = {
  id: number;
  name: string;
  description: string | null;
  duration_minutes: number;
  price: number | null;
  active: boolean;
  created_at: string;
};

export type StaffAvailabilityInput = {
  weekday: number;
  start_time: string;
  end_time: string;
  slot_duration_minutes: number;
  active: boolean;
};

export type StaffInput = {
  name: string;
  phone: string | null;
  email: string | null;
  active: boolean;
  service_ids: number[];
  availability: StaffAvailabilityInput[];
};
