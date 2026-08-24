export type DashboardSummary = {
  today_appointments: number;
  upcoming_appointments: number;
  total_customers: number;
  active_staff: number;
};

export type DashboardAppointment = {
  id: number;
  service_id: number;
  assigned_staff_id: number | null;
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

export type ClientAppointment = { id: number; service: string; staff: string | null; start_at: string; end_at: string; status: string };
export type DashboardClient = {
  id: number; name: string; phone: string; email: string | null; is_active: boolean;
  marketing_opt_in: boolean; last_activity_at: string | null;
  last_appointment: ClientAppointment | null; total_appointment_count: number;
};
export type ClientConversation = { id: number; last_message: string | null; last_activity_at: string; message_count: number };
export type ClientDetail = DashboardClient & {
  birthday: string | null; notes: string | null; created_at: string; updated_at: string;
  marketing_opt_in_at: string | null; marketing_opt_in_source: string | null; marketing_opt_out_at: string | null;
  marketing_consent_asked_at: string | null; marketing_consent_status: "not_asked" | "opted_in" | "opted_out";
  upcoming_appointment: ClientAppointment | null; appointments: ClientAppointment[]; conversations: ClientConversation[];
};
export type ClientInput = {
  name: string; phone: string; email: string | null; birthday: string | null; notes: string | null;
  is_active: boolean; marketing_opt_in: boolean; marketing_opt_in_source: string | null;
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

export type ServiceInput = {
  name: string;
  description: string | null;
  duration_minutes: number;
  price: number;
  active: boolean;
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

export type BusinessHour = {
  id: number;
  weekday: number;
  is_open: boolean;
  open_time: string | null;
  close_time: string | null;
  created_at: string;
  updated_at: string;
};

export type BusinessHourInput = Omit<BusinessHour, "id" | "created_at" | "updated_at">;

export type BusinessClosure = {
  id: number;
  start_date: string;
  end_date: string;
  reason: string | null;
  created_at: string;
  updated_at: string;
};

export type BusinessClosureInput = Pick<
  BusinessClosure,
  "start_date" | "end_date" | "reason"
>;

export type ConversationStatus =
  | "active"
  | "waiting"
  | "booked"
  | "completed"
  | "cancelled";

export type DashboardConversation = {
  id: number;
  customer_name: string | null;
  customer_phone: string;
  last_message_preview: string | null;
  last_activity_at: string;
  status: ConversationStatus;
  appointment_id: number | null;
  ai_summary: string | null;
  unread: boolean;
};

export type ConversationAppointment = {
  id: number;
  service_name: string;
  staff_name: string | null;
  start_at: string;
  end_at: string;
  status: string;
};

export type ConversationDetail = {
  id: number;
  customer: { id: number; name: string | null; phone: string; email: string | null };
  status: ConversationStatus;
  created_at: string;
  last_activity_at: string;
  ai_summary: string | null;
  appointment: ConversationAppointment | null;
  internal_notes: string | null;
  unread: boolean;
};

export type ConversationMessage = {
  id: number;
  sender: string;
  body: string;
  timestamp: string;
  direction: "incoming" | "outgoing";
  delivery_status: string | null;
};

export type CampaignRecipient = {
  id: number; client_id: number; phone: string; client_name: string | null;
  consent_source: string | null; consent_at: string | null; status: string;
  queued_at: string | null; sent_at: string | null; delivered_at: string | null;
  read_at: string | null; replied_at: string | null; failed_at: string | null;
  failure_code: string | null; failure_message: string | null;
};
export type PromotionCoupon = {
  id: number; code: string; description: string | null; discount_type: "percentage" | "fixed_amount";
  discount_value: number; service_id: number | null; starts_at: string | null; expires_at: string | null;
  redemption_limit: number | null; redemption_count: number; is_active: boolean;
};
export type PromotionCampaign = {
  id: number; name: string; status: string; message_template_name: string; message_template_display_name: string; message_template_language: string;
  headline: string | null; body_text: string; footer_text: string | null; flyer_url: string | null;
  audience_type: string; audience_config: Record<string, unknown> | null; scheduled_at: string | null;
  started_at: string | null; completed_at: string | null; created_at: string; updated_at: string;
  coupon: PromotionCoupon | null; recipient_counts: Record<string, number>; recipients?: CampaignRecipient[];
};
export type AudiencePreview = {
  eligible_count: number; excluded_count: number; exclusion_reasons: Record<string, number>;
  preview_rows: Array<{ client_id: number; name: string | null; phone: string; consent_source: string | null }>;
};

export type AnalyticsService = {
  service_id: number; service_name: string; active: boolean; appointment_count: number; completed_count: number;
};
export type AnalyticsStaff = {
  staff_id: number | null; staff_name: string; active: boolean | null;
  appointment_count: number; completed_count: number; upcoming_count: number;
};
export type AnalyticsCoupon = { coupon_id: number; code: string; redemption_count: number };
export type AnalyticsDashboard = {
  period: { key: string; label: string; start_date: string; end_date: string; start_at: string; end_at: string; timezone: string };
  overview: {
    total_appointments: number; confirmed_appointments: number; completed_appointments: number;
    cancelled_appointments: number; cancellation_rate: number; new_clients: number; returning_clients: number;
  };
  services: { most_booked_service: AnalyticsService | null; rows: AnalyticsService[] };
  staff: AnalyticsStaff[];
  clients: { new_clients: number; returning_clients: number; unique_clients: number; repeat_clients: number };
  promotions: {
    campaigns_created: number; campaign_recipients: number; submitted: number; sent: number; delivered: number;
    read: number; replied: number; failed: number; delivery_rate: number | null; read_rate: number | null; reply_rate: number | null;
  };
  coupons: { active_coupons: number; total_redemptions: number; most_redeemed_coupon: AnalyticsCoupon | null; rows: AnalyticsCoupon[] };
  value: { completed_service_value: number; currency: string; definition: string };
  definitions: Record<string, string>;
};
