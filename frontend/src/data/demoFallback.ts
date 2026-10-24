import type { BloodBank } from '../services/api'

export const DEMO_FALLBACK_BANKS: BloodBank[] = [
  {
    id: 901,
    name: "Demo Central Transfusion Facility",
    city: "Delhi",
    locality: "Connaught Place (Central Delhi)",
    source_type: "demo",
    source_name: "Synthetic demo dataset",
    source_facility_id: "demo:901",
    stock_reports: [
      { id: 9001, blood_bank_id: 901, blood_group: "A+", units_reported: 12, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9002, blood_bank_id: 901, blood_group: "A-", units_reported: 4, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9003, blood_bank_id: 901, blood_group: "B+", units_reported: 15, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9004, blood_bank_id: 901, blood_group: "B-", units_reported: 3, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9005, blood_bank_id: 901, blood_group: "AB+", units_reported: 6, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9006, blood_bank_id: 901, blood_group: "AB-", units_reported: 2, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9007, blood_bank_id: 901, blood_group: "O+", units_reported: 18, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9008, blood_bank_id: 901, blood_group: "O-", units_reported: 5, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" }
    ]
  },
  {
    id: 902,
    name: "North Ridge Synthetic Blood Depot",
    city: "Delhi",
    locality: "Civil Lines (North Delhi)",
    source_type: "demo",
    source_name: "Synthetic demo dataset",
    source_facility_id: "demo:902",
    stock_reports: [
      { id: 9009, blood_bank_id: 902, blood_group: "A+", units_reported: 8, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9010, blood_bank_id: 902, blood_group: "A-", units_reported: 2, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9011, blood_bank_id: 902, blood_group: "B+", units_reported: 10, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9012, blood_bank_id: 902, blood_group: "B-", units_reported: 4, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9013, blood_bank_id: 902, blood_group: "AB+", units_reported: 3, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9014, blood_bank_id: 902, blood_group: "AB-", units_reported: 1, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9015, blood_bank_id: 902, blood_group: "O+", units_reported: 14, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9016, blood_bank_id: 902, blood_group: "O-", units_reported: 3, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" }
    ]
  },
  {
    id: 903,
    name: "South District Fictional Blood Bank",
    city: "Delhi",
    locality: "Saket (South Delhi)",
    source_type: "demo",
    source_name: "Synthetic demo dataset",
    source_facility_id: "demo:903",
    stock_reports: [
      { id: 9017, blood_bank_id: 903, blood_group: "A+", units_reported: 15, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9018, blood_bank_id: 903, blood_group: "A-", units_reported: 5, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9019, blood_bank_id: 903, blood_group: "B+", units_reported: 8, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9020, blood_bank_id: 903, blood_group: "B-", units_reported: 2, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9021, blood_bank_id: 903, blood_group: "AB+", units_reported: 7, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9022, blood_bank_id: 903, blood_group: "AB-", units_reported: 2, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9023, blood_bank_id: 903, blood_group: "O+", units_reported: 20, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9024, blood_bank_id: 903, blood_group: "O-", units_reported: 4, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" }
    ]
  },
  {
    id: 904,
    name: "East Valley Demo Transfusion Center",
    city: "Delhi",
    locality: "Mayur Vihar (East Delhi)",
    source_type: "demo",
    source_name: "Synthetic demo dataset",
    source_facility_id: "demo:904",
    stock_reports: [
      { id: 9025, blood_bank_id: 904, blood_group: "A+", units_reported: 6, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9026, blood_bank_id: 904, blood_group: "A-", units_reported: 1, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9027, blood_bank_id: 904, blood_group: "B+", units_reported: 9, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9028, blood_bank_id: 904, blood_group: "B-", units_reported: 3, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9029, blood_bank_id: 904, blood_group: "AB+", units_reported: 4, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9030, blood_bank_id: 904, blood_group: "AB-", units_reported: 1, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9031, blood_bank_id: 904, blood_group: "O+", units_reported: 11, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9032, blood_bank_id: 904, blood_group: "O-", units_reported: 2, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" }
    ]
  },
  {
    id: 905,
    name: "Gomti Bank Synthetic Blood Repository",
    city: "Lucknow",
    locality: "Gomti Nagar (East Lucknow)",
    source_type: "demo",
    source_name: "Synthetic demo dataset",
    source_facility_id: "demo:905",
    stock_reports: [
      { id: 9033, blood_bank_id: 905, blood_group: "A+", units_reported: 10, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9034, blood_bank_id: 905, blood_group: "A-", units_reported: 3, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9035, blood_bank_id: 905, blood_group: "B+", units_reported: 14, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9036, blood_bank_id: 905, blood_group: "B-", units_reported: 5, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9037, blood_bank_id: 905, blood_group: "AB+", units_reported: 5, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9038, blood_bank_id: 905, blood_group: "AB-", units_reported: 2, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9039, blood_bank_id: 905, blood_group: "O+", units_reported: 16, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9040, blood_bank_id: 905, blood_group: "O-", units_reported: 4, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" }
    ]
  },
  {
    id: 906,
    name: "Awadh Central Fictional Blood Reserve",
    city: "Lucknow",
    locality: "Hazratganj (Central Lucknow)",
    source_type: "demo",
    source_name: "Synthetic demo dataset",
    source_facility_id: "demo:906",
    stock_reports: [
      { id: 9041, blood_bank_id: 906, blood_group: "A+", units_reported: 14, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9042, blood_bank_id: 906, blood_group: "A-", units_reported: 4, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9043, blood_bank_id: 906, blood_group: "B+", units_reported: 11, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9044, blood_bank_id: 906, blood_group: "B-", units_reported: 3, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9045, blood_bank_id: 906, blood_group: "AB+", units_reported: 8, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9046, blood_bank_id: 906, blood_group: "AB-", units_reported: 3, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9047, blood_bank_id: 906, blood_group: "O+", units_reported: 22, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9048, blood_bank_id: 906, blood_group: "O-", units_reported: 6, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" }
    ]
  },
  {
    id: 907,
    name: "Charbagh Metro Demo Blood Unit",
    city: "Lucknow",
    locality: "Charbagh (South Lucknow)",
    source_type: "demo",
    source_name: "Synthetic demo dataset",
    source_facility_id: "demo:907",
    stock_reports: [
      { id: 9049, blood_bank_id: 907, blood_group: "A+", units_reported: 7, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9050, blood_bank_id: 907, blood_group: "A-", units_reported: 2, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9051, blood_bank_id: 907, blood_group: "B+", units_reported: 12, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9052, blood_bank_id: 907, blood_group: "B-", units_reported: 4, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9053, blood_bank_id: 907, blood_group: "AB+", units_reported: 3, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9054, blood_bank_id: 907, blood_group: "AB-", units_reported: 1, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9055, blood_bank_id: 907, blood_group: "O+", units_reported: 13, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9056, blood_bank_id: 907, blood_group: "O-", units_reported: 3, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" }
    ]
  },
  {
    id: 908,
    name: "Old City Synthetic Transfusion Depot",
    city: "Lucknow",
    locality: "Chowk (Old Lucknow)",
    source_type: "demo",
    source_name: "Synthetic demo dataset",
    source_facility_id: "demo:908",
    stock_reports: [
      { id: 9057, blood_bank_id: 908, blood_group: "A+", units_reported: 9, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9058, blood_bank_id: 908, blood_group: "A-", units_reported: 3, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9059, blood_bank_id: 908, blood_group: "B+", units_reported: 8, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9060, blood_bank_id: 908, blood_group: "B-", units_reported: 2, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9061, blood_bank_id: 908, blood_group: "AB+", units_reported: 4, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9062, blood_bank_id: 908, blood_group: "AB-", units_reported: 2, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9063, blood_bank_id: 908, blood_group: "O+", units_reported: 15, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" },
      { id: 9064, blood_bank_id: 908, blood_group: "O-", units_reported: 5, source_name: "Synthetic demo dataset", data_timestamp: "2026-10-15T12:00:00Z", verification_status: "demo" }
    ]
  }
]
