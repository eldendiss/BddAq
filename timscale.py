def calculate_timer_params(target_frequency, tim_base_clock=72000000, tolerance=0.05):
    arr_max = 2 ** 16 - 1
    psc_max = 2 ** 16 - 1
    
    # Calculate the maximum and minimum update frequencies
    target_update_f_max = tim_base_clock
    target_update_f_min = tim_base_clock / (psc_max * (arr_max + 1))
    
    if target_frequency > target_update_f_max or target_frequency < target_update_f_min:
        print("Target frequency is not in range of MIN/MAX!")
        return None, None

    for psc in range(psc_max + 1):
        for arr in range(arr_max + 1):
            # Calculate the actual frequency
            actual_frequency = tim_base_clock / ((psc + 1) * (arr + 1))
            
            # Check if the actual frequency is close to the target frequency within the specified tolerance
            if abs(actual_frequency - target_frequency) / target_frequency <= tolerance:
                return arr, psc
    
    # If no suitable values found
    return None, None